from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import secrets

from pydantic import BaseModel, EmailStr, field_validator

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.core_moderation_analytics import CommenterAccount

router = APIRouter(prefix="/commenters", tags=["Commenters"])


# ── SCHEMAS ───────────────────────────────────────────────────────────────────

class CommenterRegister(BaseModel):
    email: EmailStr
    username: str
    display_name: Optional[str] = None
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be 3–30 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, underscores")
        return v.lower()


class CommenterLogin(BaseModel):
    email: EmailStr
    password: str


class CommenterUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class CommenterResponse(BaseModel):
    id: UUID
    email: str
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    status: str
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CommenterTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    commenter: CommenterResponse


class RefreshRequest(BaseModel):
    refresh_token: str


# ── DEPENDENCY ────────────────────────────────────────────────────────────────

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security

bearer = HTTPBearer(auto_error=False)

async def get_current_commenter(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    db: AsyncSession = Depends(get_db),
) -> CommenterAccount:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "commenter_access":
        raise HTTPException(status_code=401, detail="Invalid or expired commenter token")
    commenter_id = payload.get("sub")
    result = await db.execute(
        select(CommenterAccount).where(
            CommenterAccount.id == UUID(commenter_id),
            CommenterAccount.deleted_at.is_(None),
        )
    )
    commenter = result.scalar_one_or_none()
    if not commenter:
        raise HTTPException(status_code=401, detail="Commenter not found")
    if commenter.status != "active":
        raise HTTPException(status_code=403, detail=f"Account is {commenter.status}")
    return commenter


async def get_optional_commenter(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[CommenterAccount]:
    """Returns commenter if authenticated, None if not — for endpoints that allow both."""
    if not credentials:
        return None
    try:
        return await get_current_commenter(credentials, db)
    except HTTPException:
        return None


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=CommenterResponse, status_code=201)
async def register(payload: CommenterRegister, db: AsyncSession = Depends(get_db)):
    # Check email
    existing = await db.execute(
        select(CommenterAccount).where(CommenterAccount.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check username
    existing_u = await db.execute(
        select(CommenterAccount).where(CommenterAccount.username == payload.username)
    )
    if existing_u.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    verification_token = secrets.token_urlsafe(32)
    commenter = CommenterAccount(
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name or payload.username,
        password_hash=get_password_hash(payload.password),
        email_verification_token=verification_token,
        status="active",  # auto-activate for now; swap to pending_verification when SMTP ready
        email_verified=False,
    )
    db.add(commenter)
    return commenter


@router.post("/login", response_model=CommenterTokenResponse)
async def login(payload: CommenterLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CommenterAccount).where(
            CommenterAccount.email == payload.email,
            CommenterAccount.deleted_at.is_(None),
        )
    )
    commenter = result.scalar_one_or_none()

    if not commenter or not verify_password(payload.password, commenter.password_hash):
        if commenter:
            commenter.failed_login_attempts += 1
            if commenter.failed_login_attempts >= 5:
                commenter.locked_until = datetime.utcnow() + timedelta(minutes=15)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if commenter.locked_until and commenter.locked_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="Account locked. Try again later.")

    if commenter.status not in ("active",):
        raise HTTPException(status_code=403, detail=f"Account is {commenter.status}")

    commenter.failed_login_attempts = 0
    commenter.locked_until = None
    commenter.last_login_at = datetime.utcnow()

    token_data = {"sub": str(commenter.id), "type": "commenter_access"}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({**token_data, "type": "commenter_refresh"})

    return CommenterTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        commenter=commenter,
    )


@router.post("/refresh", response_model=CommenterTokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "commenter_refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(
        select(CommenterAccount).where(
            CommenterAccount.id == UUID(data["sub"]),
            CommenterAccount.deleted_at.is_(None),
        )
    )
    commenter = result.scalar_one_or_none()
    if not commenter:
        raise HTTPException(status_code=401, detail="Commenter not found")

    token_data = {"sub": str(commenter.id), "type": "commenter_access"}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token({**token_data, "type": "commenter_refresh"})

    return CommenterTokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        commenter=commenter,
    )


@router.get("/me", response_model=CommenterResponse)
async def get_me(commenter: CommenterAccount = Depends(get_current_commenter)):
    return commenter


@router.patch("/me", response_model=CommenterResponse)
async def update_me(
    payload: CommenterUpdate,
    db: AsyncSession = Depends(get_db),
    commenter: CommenterAccount = Depends(get_current_commenter),
):
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(commenter, field, value)
    commenter.updated_at = datetime.utcnow()
    return commenter


@router.get("/verify-email/{token}", status_code=200)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CommenterAccount).where(CommenterAccount.email_verification_token == token)
    )
    commenter = result.scalar_one_or_none()
    if not commenter:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    commenter.email_verified = True
    commenter.email_verification_token = None
    return {"message": "Email verified successfully"}
