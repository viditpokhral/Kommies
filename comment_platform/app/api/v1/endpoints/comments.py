import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.db.session import get_db
from app.models import (
    Website, Thread, Comment, CommentHistory, CommentVote,
    NotificationSettings, ModerationQueue,
)
from app.schemas.core import (
    CommentCreate, CommentUpdate, CommentResponse,
    ThreadResponse, VoteRequest, PaginatedResponse,
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


@router.get("/{api_key}/threads/{identifier}/comments", response_model=PaginatedResponse)
async def list_comments(
    api_key: str,
    identifier: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    website = await _get_website_by_api_key(api_key, db)
    result = await db.execute(
        select(Thread).where(Thread.website_id == website.id, Thread.identifier == identifier)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    count_result = await db.execute(
        select(func.count()).select_from(Comment).where(
            Comment.thread_id == thread.id,
            Comment.status == "published",
            Comment.is_deleted == False,
            Comment.parent_id.is_(None),
        )
    )
    total = count_result.scalar()
    offset = (page - 1) * page_size
    comments_result = await db.execute(
        select(Comment).where(
            Comment.thread_id == thread.id,
            Comment.status == "published",
            Comment.is_deleted == False,
            Comment.parent_id.is_(None),
        ).order_by(Comment.created_at.asc()).offset(offset).limit(page_size)
    )
    comments = comments_result.scalars().all()
    return PaginatedResponse(
        items=[CommentResponse.model_validate(c) for c in comments],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


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

    needs_moderation = website.settings.get("require_moderation", False)
    if spam_result.is_spam:
        initial_status = "spam"
    elif needs_moderation or spam_result.suggested_status == "pending":
        initial_status = "pending"
    else:
        initial_status = "published"

    # 2. Create comment
    comment = Comment(
        thread_id=thread.id,
        parent_id=payload.parent_id,
        author_name=payload.author_name,
        author_email=payload.author_email,
        author_website=payload.author_website,
        author_ip=author_ip,
        author_user_agent=request.headers.get("user-agent"),
        content=payload.content,
        status=initial_status,
        spam_score=spam_result.score,
    )
    db.add(comment)
    await db.flush()

    # 3. Auto-queue flagged comments
    if initial_status in ("pending", "spam") and spam_result.reasons:
        db.add(ModerationQueue(
            comment_id=comment.id,
            website_id=website.id,
            reason=", ".join(spam_result.reasons[:3]),
            flagged_by="spam_filter",
            severity="high" if spam_result.is_spam else "medium",
        ))

    # 4. Notification emails (fire-and-forget)
    ns_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.website_id == website.id)
    )
    ns = ns_result.scalar_one_or_none()

    if ns and ns.notification_email and initial_status != "spam":
        if ns.notify_new_comments:
            asyncio.create_task(email_service.send_new_comment_notification(
                notify_email=ns.notification_email,
                website_name=website.name,
                author_name=payload.author_name,
                comment_content=payload.content,
                thread_url=url,
                moderation_url=f"/dashboard/websites/{website.id}/moderation",
            ))
        if initial_status == "pending" and ns.notify_moderation_needed:
            count_res = await db.execute(
                select(func.count()).select_from(Comment)
                .join(Thread, Thread.id == Comment.thread_id)
                .where(Thread.website_id == website.id, Comment.status == "pending")
            )
            pending_count = count_res.scalar() or 1
            asyncio.create_task(email_service.send_moderation_needed(
                notify_email=ns.notification_email,
                website_name=website.name,
                pending_count=pending_count,
                moderation_url=f"/dashboard/websites/{website.id}/moderation",
            ))

    # 5. Reply notification to parent comment author
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

    # 6. Webhook
    await webhook_service.comment_created(website, comment, thread, db)
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
