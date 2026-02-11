from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import date, timedelta
from typing import List
from pydantic import BaseModel

from app.db.session import get_db
from app.models import SuperUser, DailyUsage, WebsiteStat, Website
from app.api.deps import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class UsageSummary(BaseModel):
    usage_date: date
    total_requests: int
    get_requests: int
    post_requests: int
    error_count: int
    avg_response_time_ms: int | None

    model_config = {"from_attributes": True}


class WebsiteStatResponse(BaseModel):
    stat_date: date
    total_comments: int
    approved_comments: int
    spam_comments: int
    unique_commenters: int
    total_threads: int

    model_config = {"from_attributes": True}


@router.get("/usage", response_model=List[UsageSummary])
async def get_usage(
    days: int = Query(30, ge=1, le=365),
    website_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    since = date.today() - timedelta(days=days)

    query = select(DailyUsage).where(
        DailyUsage.super_user_id == current_user.id,
        DailyUsage.usage_date >= since,
    )
    if website_id:
        query = query.where(DailyUsage.website_id == website_id)

    result = await db.execute(query.order_by(DailyUsage.usage_date.desc()))
    return result.scalars().all()


@router.get("/websites/{website_id}/stats", response_model=List[WebsiteStatResponse])
async def get_website_stats(
    website_id: UUID,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    # Verify ownership
    result = await db.execute(
        select(Website).where(
            Website.id == website_id,
            Website.super_user_id == current_user.id,
            Website.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Website not found")

    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(WebsiteStat)
        .where(WebsiteStat.website_id == website_id, WebsiteStat.stat_date >= since)
        .order_by(WebsiteStat.stat_date.desc())
    )
    return result.scalars().all()


@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    since = date.today() - timedelta(days=30)

    result = await db.execute(
        select(
            func.sum(DailyUsage.total_requests).label("total_requests"),
            func.sum(DailyUsage.error_count).label("total_errors"),
            func.avg(DailyUsage.avg_response_time_ms).label("avg_response_time"),
        ).where(
            DailyUsage.super_user_id == current_user.id,
            DailyUsage.usage_date >= since,
        )
    )
    row = result.one()

    website_count = await db.execute(
        select(func.count()).select_from(Website).where(
            Website.super_user_id == current_user.id,
            Website.deleted_at.is_(None),
        )
    )

    return {
        "period_days": 30,
        "total_requests": row.total_requests or 0,
        "total_errors": row.total_errors or 0,
        "avg_response_time_ms": round(row.avg_response_time or 0, 2),
        "active_websites": website_count.scalar(),
    }
