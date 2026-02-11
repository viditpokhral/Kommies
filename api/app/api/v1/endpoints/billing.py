from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.db.session import get_db
from app.models import SuperUser, Plan, Subscription, Invoice
from app.api.deps import get_current_user

router = APIRouter(prefix="/billing", tags=["Billing"])


class PlanResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    monthly_price: Decimal
    yearly_price: Optional[Decimal]
    requests_per_month: int
    max_websites: Optional[int]
    features: dict
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: UUID
    plan_id: UUID
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: datetime
    requests_used: int
    requests_limit: int
    usage_percentage: float
    auto_renew: bool
    trial_ends_at: Optional[datetime]

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    status: str
    amount: Decimal
    total_amount: Decimal
    currency: str
    period_start: datetime
    period_end: datetime
    paid_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)
    )
    return result.scalars().all()


@router.get("/plans/{slug}", response_model=PlanResponse)
async def get_plan(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.slug == slug, Plan.is_active == True))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_my_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.super_user_id == current_user.id,
            Subscription.status == "active",
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return None

    response = SubscriptionResponse.model_validate(sub)
    response.usage_percentage = round((sub.requests_used / sub.requests_limit) * 100, 2) if sub.requests_limit else 0
    return response


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Invoice)
        .where(Invoice.super_user_id == current_user.id)
        .order_by(Invoice.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
