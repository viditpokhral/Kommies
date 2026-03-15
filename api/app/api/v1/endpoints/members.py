from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.db.session import get_db
from app.models import SuperUser
from app.models.auth_billing import SiteMember
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/websites/{website_id}/members", tags=["Members"])


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "moderator"  # moderator | viewer


class UpdateRoleRequest(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: UUID
    super_user_id: UUID
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=None)
async def list_members(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_role("viewer")),
):
    website, _ = access
    result = await db.execute(
        select(SiteMember, SuperUser)
        .join(SuperUser, SuperUser.id == SiteMember.super_user_id)
        .where(SiteMember.website_id == website_id)
        .order_by(SiteMember.created_at)
    )
    rows = result.all()
    return {
        "items": [
            {
                "id": str(m.id),
                "super_user_id": str(m.super_user_id),
                "email": u.email,
                "full_name": u.full_name,
                "role": m.role,
                "created_at": m.created_at.isoformat(),
            }
            for m, u in rows
        ]
    }


@router.post("/", status_code=201)
async def invite_member(
    website_id: UUID,
    payload: InviteMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
    access=Depends(require_role("owner")),
):
    website, _ = access

    valid_roles = ("moderator", "viewer")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

    # Find user by email
    result = await db.execute(
        select(SuperUser).where(SuperUser.email == payload.email, SuperUser.deleted_at.is_(None))
    )
    invitee = result.scalar_one_or_none()
    if not invitee:
        raise HTTPException(status_code=404, detail="No user found with that email")

    # Check not already a member
    existing = await db.execute(
        select(SiteMember).where(
            SiteMember.website_id == website_id,
            SiteMember.super_user_id == invitee.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member of this website")

    db.add(SiteMember(
        website_id=website_id,
        super_user_id=invitee.id,
        role=payload.role,
        invited_by=current_user.id,
    ))
    return {"message": f"{invitee.email} added as {payload.role}"}


@router.patch("/{member_id}", status_code=200)
async def update_member_role(
    website_id: UUID,
    member_id: UUID,
    payload: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_role("owner")),
):
    valid_roles = ("moderator", "viewer")
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {valid_roles}")

    result = await db.execute(
        select(SiteMember).where(SiteMember.id == member_id, SiteMember.website_id == website_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot change the owner's role")

    member.role = payload.role
    member.updated_at = datetime.utcnow()
    return {"message": f"Role updated to {payload.role}"}


@router.delete("/{member_id}", status_code=200)
async def remove_member(
    website_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_role("owner")),
):
    result = await db.execute(
        select(SiteMember).where(SiteMember.id == member_id, SiteMember.website_id == website_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")

    await db.delete(member)
    return {"message": "Member removed"}
