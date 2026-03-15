import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.db.session import get_db
from app.models.core_moderation_analytics import Website
from app.models import (
    Website, Thread, Comment, CommentHistory, CommentVote,
    NotificationSettings, ModerationQueue, ModerationReport,
)
from app.schemas.core import (
    CommentCreate, CommentUpdate, CommentResponse, FlagRequest,
    ThreadResponse, VoteRequest,
)
from app.services.spam import spam_service
from app.services.email import email_service
from app.services.webhooks import webhook_service

router = APIRouter(prefix="/comments", tags=["Comments (Public API)"])


async def _get_website_by_api_key(api_key: str, db: AsyncSession) -> Website:
    result = await db.execute(
        select(Website).where(Website.api_key == api_key, Website.deleted_at.is_(None))
    )
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if website.status != "active":
        raise HTTPException(status_code=403, detail="Website is suspended")
    return website


async def _get_or_create_thread(
    website: Website, identifier: str, title: Optional[str], url: Optional[str], db: AsyncSession
) -> Thread:
    result = await db.execute(
        select(Thread).where(Thread.website_id == website.id, Thread.identifier == identifier)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        thread = Thread(website_id=website.id, identifier=identifier, title=title, url=url)
        db.add(thread)
        await db.flush()
    return thread


async def _increment_thread_count(thread_id: UUID, db: AsyncSession, delta: int = 1):
    """Increment or decrement thread.comment_count atomically."""
    await db.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(
            comment_count=Thread.comment_count + delta,
            last_comment_at=datetime.utcnow() if delta > 0 else Thread.last_comment_at,
        )
    )


@router.get("/{api_key}/threads/{identifier}", response_model=ThreadResponse)
async def get_thread(api_key: str, identifier: str, db: AsyncSession = Depends(get_db)):
    website = await _get_website_by_api_key(api_key, db)
    result = await db.execute(
        select(Thread).where(
            Thread.website_id == website.id,
            Thread.identifier == identifier,
            Thread.is_deleted == False,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.get("/{api_key}/threads/{identifier}/comments", response_model=None)
async def list_comments(
    api_key: str,
    identifier: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)

    result = await db.execute(
        select(Thread).where(Thread.website_id == website.id, Thread.identifier == identifier)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

    filters = [
        Comment.thread_id == thread.id,
        Comment.status == "published",
        Comment.is_deleted == False,
    ]

    count_result = await db.execute(
        select(func.count()).select_from(Comment).where(*filters)
    )
    total = count_result.scalar() or 0

    comments_result = await db.execute(
        select(Comment)
        .where(*filters)
        .order_by(Comment.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    comments = comments_result.scalars().all()

    return {
        "items": [CommentResponse.model_validate(c).model_dump() for c in comments],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/{api_key}/threads/{identifier}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    api_key: str,
    identifier: str,
    payload: CommentCreate,
    request: Request,
    title: Optional[str] = Query(None),
    url: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)

    if not website.settings.get("allow_anonymous", True) and not payload.author_email:
        raise HTTPException(status_code=400, detail="Email is required for this website")

    thread = await _get_or_create_thread(website, identifier, title, url, db)

    if thread.status in ("locked", "archived"):
        raise HTTPException(status_code=403, detail=f"Thread is {thread.status}")

    max_length = website.settings.get("max_comment_length", 5000)
    if len(payload.content) > max_length:
        raise HTTPException(status_code=400, detail=f"Comment exceeds max length of {max_length}")

    author_ip = str(request.client.host) if request.client else None

    # 1. Spam check
    spam_result = await spam_service.check(
        content=payload.content,
        author_name=payload.author_name,
        author_email=payload.author_email,
        author_ip=author_ip,
        website=website,
        db=db,
    )
    if spam_result.is_banned:
        raise HTTPException(status_code=403, detail="You are not allowed to post on this website")

    # No approval flow — spam goes to spam, everything else is published
    initial_status = "spam" if spam_result.is_spam else "published"

    # 2. Create comment
    comment = Comment(
        thread_id=thread.id,
        parent_id=payload.parent_id,
        commenter_id=commenter.id if commenter else None,
        author_name=commenter.display_name if commenter else payload.author_name,
        author_email=commenter.email if commenter else payload.author_email,
        author_website=payload.author_website,
        author_ip=author_ip,
        author_user_agent=request.headers.get("user-agent"),
        content=payload.content,
        status=initial_status,
        spam_score=spam_result.score,
    )
    db.add(comment)
    await db.flush()

    # 3. Update thread count and website total if published
    if initial_status == "published":
        await _increment_thread_count(thread.id, db, delta=1)
        await db.execute(
            update(Website)
            .where(Website.id == website.id)
            .values(total_comments=Website.total_comments + 1)
        )

    # 4. Auto-queue spam
    if initial_status == "spam" and spam_result.reasons:
        db.add(ModerationQueue(
            comment_id=comment.id,
            website_id=website.id,
            reason=", ".join(spam_result.reasons[:3]),
            flagged_by="spam_filter",
            severity="high",
        ))

    # 5. Notification emails (fire-and-forget)
    ns_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.website_id == website.id)
    )
    ns = ns_result.scalar_one_or_none()

    if ns and ns.notification_email and initial_status == "published":
        if ns.notify_new_comments:
            asyncio.create_task(email_service.send_new_comment_notification(
                notify_email=ns.notification_email,
                website_name=website.name,
                author_name=payload.author_name,
                comment_content=payload.content,
                thread_url=url,
                moderation_url=f"/dashboard/websites/{website.id}/moderation",
            ))

    # 6. Reply notification to parent comment author
    if payload.parent_id and initial_status == "published":
        parent_res = await db.execute(select(Comment).where(Comment.id == payload.parent_id))
        parent = parent_res.scalar_one_or_none()
        if parent and parent.author_email and parent.author_email != payload.author_email:
            if ns and ns.notify_replies:
                asyncio.create_task(email_service.send_reply_notification(
                    author_email=parent.author_email,
                    author_name=parent.author_name,
                    replier_name=payload.author_name,
                    reply_content=payload.content,
                    thread_url=url,
                ))

    # 7. Webhook
    await webhook_service.comment_created(website, comment, thread, db)

    # Re-fetch clean comment (no relationships needed — flat API)
    await db.refresh(comment)
    return comment


@router.patch("/{api_key}/comments/{comment_id}", response_model=CommentResponse)
async def edit_comment(
    api_key: str,
    comment_id: UUID,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)
    result = await db.execute(
        select(Comment).join(Thread, Thread.id == Comment.thread_id).where(
            Comment.id == comment_id,
            Thread.website_id == website.id,
            Comment.is_deleted == False,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    db.add(CommentHistory(comment_id=comment.id, content=comment.content, edited_by="author"))
    comment.content = payload.content
    comment.is_edited = True
    comment.edited_at = datetime.utcnow()
    comment.edit_count += 1
    return comment


@router.post("/{api_key}/comments/{comment_id}/vote", response_model=CommentResponse)
async def vote_comment(
    api_key: str,
    comment_id: UUID,
    payload: VoteRequest,
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)
    if not website.settings.get("allow_voting", True):
        raise HTTPException(status_code=403, detail="Voting is disabled for this website")
    if payload.vote_type not in ("upvote", "downvote"):
        raise HTTPException(status_code=400, detail="vote_type must be 'upvote' or 'downvote'")

    result = await db.execute(
        select(Comment).join(Thread).where(
            Comment.id == comment_id,
            Thread.website_id == website.id,
            Comment.status == "published",
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing = await db.execute(
        select(CommentVote).where(
            CommentVote.comment_id == comment_id,
            CommentVote.voter_identifier == payload.voter_identifier,
        )
    )
    vote = existing.scalar_one_or_none()
    if vote:
        if vote.vote_type == payload.vote_type:
            await db.delete(vote)
        else:
            vote.vote_type = payload.vote_type
    else:
        db.add(CommentVote(
            comment_id=comment_id,
            voter_identifier=payload.voter_identifier,
            vote_type=payload.vote_type,
        ))

    await db.flush()
    await db.refresh(comment)
    return comment


@router.post("/{api_key}/comments/{comment_id}/flag", status_code=201)
async def flag_comment(
    api_key: str,
    comment_id: UUID,
    payload: FlagRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)

    result = await db.execute(
        select(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(
            Comment.id == comment_id,
            Thread.website_id == website.id,
            Comment.is_deleted == False,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    valid_reasons = ("spam", "offensive", "off_topic", "misinformation", "other")
    if payload.reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"reason must be one of: {valid_reasons}")

    existing = await db.execute(
        select(ModerationReport).where(
            ModerationReport.comment_id == comment_id,
            ModerationReport.reporter_identifier == payload.reporter_identifier,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already reported this comment")

    reporter_ip = str(request.client.host) if request.client else None

    db.add(ModerationReport(
        comment_id=comment_id,
        reporter_identifier=payload.reporter_identifier,
        reason=payload.reason,
        description=payload.description,
        reporter_ip=reporter_ip,
        status="pending",
    ))
    db.add(ModerationQueue(
        comment_id=comment_id,
        website_id=website.id,
        reason=f"User report: {payload.reason}",
        flagged_by="user_report",
        severity="medium",
    ))

    return {"message": "Comment reported successfully"}


@router.delete("/{api_key}/comments/{comment_id}", status_code=200)
async def delete_own_comment(
    api_key: str,
    comment_id: UUID,
    request: Request,
    author_email: str = Query(..., description="Must match the email used when posting"),
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)

    result = await db.execute(
        select(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(
            Comment.id == comment_id,
            Thread.website_id == website.id,
            Comment.is_deleted == False,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_email != author_email:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    was_published = comment.status == "published"

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    comment.deleted_by = "author"
    comment.status = "deleted"

    # Decrement count only if it was a visible comment
    if was_published:
        await _increment_thread_count(comment.thread_id, db, delta=-1)

    return {"message": "Comment deleted successfully"}