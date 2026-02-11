import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.models import SuperUser, Website, Comment, Thread, ModerationQueue, ModerationReport
from app.schemas.core import CommentResponse, PaginatedResponse
from app.api.deps import get_current_user
from app.services.webhooks import webhook_service
from app.services.email import email_service

router = APIRouter(prefix="/moderation", tags=["Moderation"])


class ModerationAction(BaseModel):
    action: str  # approve, reject, spam, trash
    notes: Optional[str] = None


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


@router.get("/{website_id}/pending", response_model=PaginatedResponse)
async def list_pending_comments(
    website_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    await _get_owned_website(website_id, current_user, db)

    count_result = await db.execute(
        select(func.count()).select_from(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, Comment.status == "pending", Comment.is_deleted == False)
    )
    total = count_result.scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, Comment.status == "pending", Comment.is_deleted == False)
        .order_by(Comment.created_at.asc()).offset(offset).limit(page_size)
    )
    comments = result.scalars().all()
    return PaginatedResponse(
        items=[CommentResponse.model_validate(c) for c in comments],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/{website_id}/comments/{comment_id}/action", response_model=CommentResponse)
async def moderate_comment(
    website_id: UUID,
    comment_id: UUID,
    payload: ModerationAction,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    website = await _get_owned_website(website_id, current_user, db)

    result = await db.execute(
        select(Comment).join(Thread, Thread.id == Comment.thread_id)
        .where(Comment.id == comment_id, Thread.website_id == website_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    action_map = {"approve": "published", "reject": "pending", "spam": "spam", "trash": "trash"}
    if payload.action not in action_map:
        raise HTTPException(status_code=400, detail=f"Invalid action. Choose from: {list(action_map.keys())}")

    comment.status = action_map[payload.action]

    db.add(ModerationQueue(
        comment_id=comment.id,
        website_id=website_id,
        reason=f"Manual moderation: {payload.action}",
        flagged_by="moderator",
        reviewed_by=current_user.id,
        reviewed_at=datetime.utcnow(),
        action_taken="approved" if payload.action == "approve" else payload.action,
        reviewer_notes=payload.notes,
    ))

    # Fire appropriate webhook
    if payload.action == "approve":
        await webhook_service.comment_approved(website, comment, db)
    elif payload.action == "spam":
        await webhook_service.comment_spam(website, comment, db)

    return comment


@router.delete("/{website_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    website_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    website = await _get_owned_website(website_id, current_user, db)

    result = await db.execute(
        select(Comment).join(Thread, Thread.id == Comment.thread_id)
        .where(Comment.id == comment_id, Thread.website_id == website_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    comment.deleted_by = "moderator"
    comment.status = "deleted"
    await webhook_service.comment_deleted(website, comment, db)


@router.get("/{website_id}/reports", response_model=PaginatedResponse)
async def list_reports(
    website_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    await _get_owned_website(website_id, current_user, db)

    count_result = await db.execute(
        select(func.count()).select_from(ModerationReport)
        .join(Comment, Comment.id == ModerationReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, ModerationReport.status == "pending")
    )
    total = count_result.scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        select(ModerationReport)
        .join(Comment, Comment.id == ModerationReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.website_id == website_id, ModerationReport.status == "pending")
        .order_by(ModerationReport.created_at.desc()).offset(offset).limit(page_size)
    )
    return PaginatedResponse(
        items=result.scalars().all(),
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
