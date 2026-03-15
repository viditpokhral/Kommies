from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.models import SuperUser
from app.models.core_moderation_analytics import Website, Comment, Thread
from app.api.deps import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


class TenantStatusUpdate(BaseModel):
    status: str  # active | suspended | deleted


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    company_name: Optional[str]
    status: str
    email_verified: bool
    is_admin: bool
    created_at: datetime
    website_count: int = 0
    total_comments: int = 0

    model_config = {"from_attributes": True}


@router.get("/tenants", response_model=None)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: SuperUser = Depends(require_admin),
):
    filters = [SuperUser.deleted_at.is_(None), SuperUser.is_admin == False]
    if status:
        filters.append(SuperUser.status == status)

    total = (await db.execute(select(func.count()).select_from(SuperUser).where(*filters))).scalar()
    users = (await db.execute(
        select(SuperUser).where(*filters)
        .order_by(SuperUser.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = []
    for u in users:
        wc = (await db.execute(
            select(func.count()).select_from(Website)
            .where(Website.super_user_id == u.id, Website.deleted_at.is_(None))
        )).scalar()
        tc = (await db.execute(
            select(func.sum(Website.total_comments))
            .where(Website.super_user_id == u.id, Website.deleted_at.is_(None))
        )).scalar() or 0
        items.append({
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "company_name": u.company_name,
            "status": u.status,
            "email_verified": u.email_verified,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
            "website_count": wc,
            "total_comments": tc,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/tenants/{user_id}", response_model=None)
async def get_tenant(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: SuperUser = Depends(require_admin),
):
    user = (await db.execute(
        select(SuperUser).where(SuperUser.id == user_id, SuperUser.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    websites = (await db.execute(
        select(Website).where(Website.super_user_id == user_id, Website.deleted_at.is_(None))
    )).scalars().all()

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "company_name": user.company_name,
        "status": user.status,
        "email_verified": user.email_verified,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
        "websites": [
            {
                "id": str(w.id),
                "name": w.name,
                "domain": w.domain,
                "status": w.status,
                "total_comments": w.total_comments,
                "total_threads": w.total_threads,
                "created_at": w.created_at.isoformat(),
            }
            for w in websites
        ],
    }


@router.patch("/tenants/{user_id}/status", status_code=200)
async def update_tenant_status(
    user_id: UUID,
    payload: TenantStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: SuperUser = Depends(require_admin),
):
    valid = ("active", "suspended", "deleted")
    if payload.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")

    user = (await db.execute(
        select(SuperUser).where(SuperUser.id == user_id, SuperUser.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot modify another admin")

    if payload.status == "deleted":
        user.deleted_at = datetime.utcnow()
    user.status = payload.status
    return {"message": f"Tenant status updated to {payload.status}"}


@router.get("/comments", response_model=None)
async def list_all_comments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: SuperUser = Depends(require_admin),
):
    filters = [Comment.is_deleted == False]
    if status:
        filters.append(Comment.status == status)

    total = (await db.execute(select(func.count()).select_from(Comment).where(*filters))).scalar()
    comments = (await db.execute(
        select(Comment).where(*filters)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "author_name": c.author_name,
                "author_email": c.author_email,
                "content": c.content[:200],
                "status": c.status,
                "thread_id": str(c.thread_id),
                "created_at": c.created_at.isoformat(),
            }
            for c in comments
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats", response_model=None)
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    _: SuperUser = Depends(require_admin),
):
    tenant_count = (await db.execute(
        select(func.count()).select_from(SuperUser)
        .where(SuperUser.deleted_at.is_(None), SuperUser.is_admin == False)
    )).scalar()
    website_count = (await db.execute(
        select(func.count()).select_from(Website).where(Website.deleted_at.is_(None))
    )).scalar()
    comment_count = (await db.execute(
        select(func.count()).select_from(Comment).where(Comment.is_deleted == False)
    )).scalar()
    spam_count = (await db.execute(
        select(func.count()).select_from(Comment).where(Comment.status == "spam")
    )).scalar()

    return {
        "tenants": tenant_count,
        "websites": website_count,
        "total_comments": comment_count,
        "spam_comments": spam_count,
    }
