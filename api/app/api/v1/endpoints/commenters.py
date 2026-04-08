import asyncio
import smtplib
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
import secrets

from pydantic import BaseModel, EmailStr, field_validator

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.core_moderation_analytics import CommenterAccount
from app.models import Thread, Comment, Website

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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


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


class CommentHistoryItem(BaseModel):
    id: UUID
    content: str
    status: str
    created_at: datetime
    is_edited: bool
    upvotes: int
    downvotes: int
    parent_id: Optional[UUID]
    thread_identifier: str
    thread_url: Optional[str]
    thread_title: Optional[str]
    website_name: str
    website_domain: str

    model_config = {"from_attributes": True}


class CommentHistoryResponse(BaseModel):
    items: List[CommentHistoryItem]
    total: int
    page: int
    page_size: int
    pages: int


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
    if not credentials:
        return None
    try:
        return await get_current_commenter(credentials, db)
    except HTTPException:
        return None


# ── EMAIL HELPER ──────────────────────────────────────────────────────────────

def _send_commenter_reset_email(to_email: str, reset_url: str) -> None:
    """Blocking SMTP send — called via asyncio.to_thread."""
    body = f"""Hi,

Someone requested a password reset for your Kommies commenter account.

Reset your password here:
{reset_url}

This link expires in 1 hour. If you didn't request this, ignore this email.

— Kommies
"""
    msg = MIMEText(body)
    msg["Subject"] = "Reset your Kommies password"
    msg["From"]    = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
    msg["To"]      = to_email

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=CommenterResponse, status_code=201)
async def register(payload: CommenterRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(CommenterAccount).where(CommenterAccount.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

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
        status="active",
        email_verified=False,
    )
    db.add(commenter)
    await db.flush()
    await db.refresh(commenter)
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


@router.delete("/me", status_code=200)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    commenter: CommenterAccount = Depends(get_current_commenter),
):
    """Soft-delete the commenter account. Comments are kept but anonymised."""
    commenter.deleted_at = datetime.utcnow()
    commenter.status     = "deleted"
    # Anonymise comments — strip PII but keep content
    await db.execute(
        __import__("sqlalchemy", fromlist=["update"]).update(Comment)
        .where(Comment.commenter_id == commenter.id)
        .values(
            author_name="[deleted]",
            author_email=None,
            commenter_id=None,
        )
    )
    return {"message": "Account deleted"}


@router.get("/me/comments", response_model=CommentHistoryResponse)
async def get_my_comments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    commenter: CommenterAccount = Depends(get_current_commenter),
):
    base_filter = [
        Comment.commenter_id == commenter.id,
        Comment.is_deleted == False,
    ]

    count_result = await db.execute(
        select(func.count()).select_from(Comment).where(*base_filter)
    )
    total = count_result.scalar() or 0

    rows_result = await db.execute(
        select(Comment, Thread, Website)
        .join(Thread,   Thread.id   == Comment.thread_id)
        .join(Website,  Website.id  == Thread.website_id)
        .where(*base_filter)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.all()

    items = [
        CommentHistoryItem(
            id=comment.id,
            content=comment.content,
            status=comment.status,
            created_at=comment.created_at,
            is_edited=comment.is_edited,
            upvotes=comment.upvotes,
            downvotes=comment.downvotes,
            parent_id=comment.parent_id,
            thread_identifier=thread.identifier,
            thread_url=thread.url,
            thread_title=thread.title,
            website_name=website.name,
            website_domain=website.domain,
        )
        for comment, thread, website in rows
    ]

    return CommentHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Always returns 200 — never reveals if email exists."""
    result = await db.execute(
        select(CommenterAccount).where(
            CommenterAccount.email == payload.email,
            CommenterAccount.deleted_at.is_(None),
        )
    )
    commenter = result.scalar_one_or_none()

    if commenter and commenter.status == "active":
        token = secrets.token_urlsafe(32)
        commenter.password_reset_token   = token
        commenter.password_reset_expires = datetime.utcnow() + timedelta(hours=1)

        portal_url = getattr(settings, "COMMENTER_PORTAL_URL", "http://localhost:8001")
        reset_url  = f"{portal_url}/commenter/reset-password/{token}/"

        try:
            await asyncio.to_thread(_send_commenter_reset_email, commenter.email, reset_url)
        except Exception:
            pass  # Don't surface SMTP errors to the user

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CommenterAccount).where(
            CommenterAccount.password_reset_token == payload.token,
            CommenterAccount.deleted_at.is_(None),
        )
    )
    commenter = result.scalar_one_or_none()

    if not commenter:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    if commenter.password_reset_expires and commenter.password_reset_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    commenter.password_hash           = get_password_hash(payload.new_password)
    commenter.password_reset_token    = None
    commenter.password_reset_expires  = None
    commenter.failed_login_attempts   = 0
    commenter.locked_until            = None

    return {"message": "Password updated. You can now sign in."}


@router.post("/change-password", status_code=200)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    commenter: CommenterAccount = Depends(get_current_commenter),
):
    if not verify_password(payload.current_password, commenter.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    commenter.password_hash = get_password_hash(payload.new_password)
    commenter.updated_at    = datetime.utcnow()
    return {"message": "Password changed successfully."}


@router.get("/verify-email/{token}", status_code=200)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CommenterAccount).where(CommenterAccount.email_verification_token == token)
    )
    commenter = result.scalar_one_or_none()
    if not commenter:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    commenter.email_verified              = True
    commenter.email_verification_token   = None
    return {"message": "Email verified successfully"}