import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.models import SuperUser, Website, Comment, Thread, ModerationQueue, ModerationReport, BannedEntity
from app.schemas.core import CommentResponse, PaginatedResponse, ModerationReportResponse
from app.api.deps import get_current_user, require_role
from app.services.webhooks import webhook_service

router = APIRouter(prefix="/moderation", tags=["Moderation"])


class ModerationAction(BaseModel):
    action: str   # spam, trash, delete
    notes: Optional[str] = None


class BanRequest(BaseModel):
    entity_type: str   # email, ip, domain
    entity_value: str
    reason: Optional[str] = None


async def _get_owned_website(website_id: UUID, current_user: SuperUser, db: AsyncSession) -> Website:
    result = await db.execute(
        select(Website).where(
            Website.id == website_id,
            Website.super_user_id == current_user.id,
            Website.deleted_at.is_(None),
        )
    )
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return website


async def _decrement_thread_count(thread_id: UUID, db: AsyncSession):
    await db.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(comment_count=Thread.comment_count - 1)
    )


# ── FLAGGED / REPORTED QUEUE ───────────────────────────────────────────────────────────────

@router.get("/{website_id}/flagged", response_model=None)
async def list_flagged_comments(
    website_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("viewer")),
):
    """Comments that have been flagged by users or caught by spam filter."""
    website, _ = access

    queue_result = await db.execute(
        select(ModerationQueue.comment_id)
        .where(
            ModerationQueue.website_id == website_id,
            ModerationQueue.action_taken.is_(None),
        )
        .distinct()
    )
    flagged_ids = [row[0] for row in queue_result.fetchall()]

    if not flagged_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

    count_result = await db.execute(
        select(func.count()).select_from(Comment)
        .where(Comment.id.in_(flagged_ids), Comment.is_deleted == False)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Comment)
        .where(Comment.id.in_(flagged_ids), Comment.is_deleted == False)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    comments = result.scalars().all()

    return {
        "items": [CommentResponse.model_validate(c).model_dump() for c in comments],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


# ── MODERATION ACTIONS ────────────────────────────────────────────────────────────────────────────

@router.post("/{website_id}/comments/{comment_id}/action", status_code=200)
async def moderate_comment(
    website_id: UUID,
    comment_id: UUID,
    payload: ModerationAction,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("moderator")),
):
    website, _ = access

    valid_actions = ("spam", "trash", "delete")
    if payload.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Choose from: {valid_actions}")

    result = await db.execute(
        select(Comment).join(Thread, Thread.id == Comment.thread_id)
        .where(Comment.id == comment_id, Thread.website_id == website_id, Comment.is_deleted == False)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    was_published = comment.status == "published"

    if payload.action == "spam":
        comment.status = "spam"
    elif payload.action == "trash":
        comment.status = "trash"
    elif payload.action == "delete":
        comment.is_deleted = True
        comment.deleted_at = datetime.utcnow()
        comment.deleted_by = "moderator"
        comment.status = "deleted"

    if was_published:
        await _decrement_thread_count(comment.thread_id, db)

    db.add(ModerationQueue(
        comment_id=comment.id,
        website_id=website_id,
        reason=f"Moderator action: {payload.action}",
        flagged_by="moderator",
        reviewed_by=current_user.id,
        reviewed_at=datetime.utcnow(),
        action_taken=payload.action,
        reviewer_notes=payload.notes,
    ))

    # Fire correct webhook per action
    if payload.action == "spam":
        await webhook_service.comment_spam(website, comment, db)
    elif payload.action == "delete":
        await webhook_service.comment_deleted(website, comment, db)
    # trash: no webhook event

    return {"message": f"Comment {payload.action}ed successfully"}


@router.delete("/{website_id}/comments/{comment_id}", status_code=200)
async def delete_comment(
    website_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("moderator")),
):
    website, _ = access

    result = await db.execute(
        select(Comment).join(Thread, Thread.id == Comment.thread_id)
        .where(Comment.id == comment_id, Thread.website_id == website_id, Comment.is_deleted == False)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    was_published = comment.status == "published"

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    comment.deleted_by = "moderator"
    comment.status = "deleted"

    if was_published:
        await _decrement_thread_count(comment.thread_id, db)

    await webhook_service.comment_deleted(website, comment, db)
    return {"message": "Comment deleted"}


# ── BAN MANAGEMENT ──────────────────────────────────────────────────────────────────────────────────

@router.post("/{website_id}/bans", status_code=201)
async def ban_entity(
    website_id: UUID,
    payload: BanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("moderator")),
):
    _, _ = access

    valid_types = ("email", "ip", "domain")
    if payload.entity_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of: {valid_types}")

    db.add(BannedEntity(
        website_id=website_id,
        entity_type=payload.entity_type,
        entity_value=payload.entity_value.lower().strip(),
        reason=payload.reason,
        banned_by="moderator",
        is_active=True,
    ))

    return {"message": f"{payload.entity_type} '{payload.entity_value}' banned successfully"}


@router.get("/{website_id}/bans", response_model=None)
async def list_bans(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("viewer")),
):
    _, _ = access

    result = await db.execute(
        select(BannedEntity)
        .where(BannedEntity.website_id == website_id, BannedEntity.is_active == True)
        .order_by(BannedEntity.created_at.desc())
    )
    bans = result.scalars().all()

    return {
        "items": [
            {
                "id": str(b.id),
                "entity_type": b.entity_type,
                "entity_value": b.entity_value,
                "reason": b.reason,
                "created_at": b.created_at.isoformat(),
            }
            for b in bans
        ],
        "total": len(bans),
    }


@router.delete("/{website_id}/bans/{ban_id}", status_code=200)
async def unban_entity(
    website_id: UUID,
    ban_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("moderator")),
):
    _, _ = access

    result = await db.execute(
        select(BannedEntity).where(BannedEntity.id == ban_id, BannedEntity.website_id == website_id)
    )
    ban = result.scalar_one_or_none()
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    ban.is_active = False
    return {"message": "Ban removed successfully"}


# ── REPORTS ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/{website_id}/reports", response_model=None)
async def list_reports(
    website_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("viewer")),
):
    _, _ = access

    count_result = await db.execute(
        select(func.count()).select_from(ModerationReport)
        .join(Comment, Comment.id == ModerationReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, ModerationReport.status == "pending")
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ModerationReport)
        .join(Comment, Comment.id == ModerationReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, ModerationReport.status == "pending")
        .order_by(ModerationReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reports = result.scalars().all()

    return {
        "items": [ModerationReportResponse.model_validate(r).model_dump() for r in reports],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }