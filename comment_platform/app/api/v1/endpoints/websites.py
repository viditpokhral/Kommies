from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import secrets

from app.db.session import get_db
from app.models import SuperUser, Website
from app.schemas.core import WebsiteCreate, WebsiteUpdate, WebsiteResponse, WebsiteSecretResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/websites", tags=["Websites"])


def _generate_api_key(prefix: str = "cpk") -> str:
    return f"{prefix}_{secrets.token_hex(32)}"


@router.post("", response_model=WebsiteSecretResponse, status_code=201)
async def create_website(
    payload: WebsiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    website = Website(
        super_user_id=current_user.id,
        name=payload.name,
        domain=payload.domain,
        allowed_origins=payload.allowed_origins or [],
        api_key=_generate_api_key("cpk"),
        api_secret=_generate_api_key("cps"),
        settings=payload.settings or {},
    )
    db.add(website)
    await db.flush()
    await db.refresh(website)
    return website


@router.get("", response_model=list[WebsiteResponse])
async def list_websites(
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Website).where(
            Website.super_user_id == current_user.id,
            Website.deleted_at.is_(None),
        ).order_by(Website.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{website_id}", response_model=WebsiteResponse)
async def get_website(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
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


@router.patch("/{website_id}", response_model=WebsiteResponse)
async def update_website(
    website_id: UUID,
    payload: WebsiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
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

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(website, field, value)
    return website


@router.delete("/{website_id}", status_code=204)
async def delete_website(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
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

    from datetime import datetime
    website.deleted_at = datetime.utcnow()
    website.status = "deleted"


@router.post("/{website_id}/rotate-keys", response_model=WebsiteSecretResponse)
async def rotate_api_keys(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
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

    website.api_key = _generate_api_key("cpk")
    website.api_secret = _generate_api_key("cps")
    return website
