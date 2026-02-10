from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.db.session import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.models import SuperUser, Session, AuditLog
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    SuperUserResponse, SuperUserUpdate, PasswordChangeRequest,
    ForgotPasswordRequest,
)
from app.api.deps import get_current_user
from app.core.config import settings
from app.services.email import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _log_event(db: AsyncSession, user_id, event_type: str, request: Request, metadata: dict = None):
    log = AuditLog(
        super_user_id=user_id,
        event_type=event_type,
        ip_address=str(request.client.host) if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata_=metadata or {},
    )
    db.add(log)


@router.post("/register", response_model=SuperUserResponse, status_code=201)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(SuperUser).where(SuperUser.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    verification_token = secrets.token_urlsafe(32)
    user = SuperUser(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        company_name=payload.company_name,
        phone=payload.phone,
        email_verification_token=verification_token,
        status="pending_verification",
    )
    db.add(user)
    await db.flush()
    await _log_event(db, user.id, "register", request)
    import asyncio
    asyncio.create_task(email_service.send_verification(
        email=user.email,
        full_name=user.full_name,
        token=verification_token,
    ))
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SuperUser).where(SuperUser.email == payload.email, SuperUser.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        await _log_event(db, user.id if user else None, "failed_login", request)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(status_code=403, detail="Account locked. Try again later.")

    if user.status not in ("active", "pending_verification"):
        raise HTTPException(status_code=403, detail=f"Account is {user.status}")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = str(request.client.host) if request.client else None

    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    session = Session(
        super_user_id=user.id,
        token=refresh_token,
        ip_address=str(request.client.host) if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await _log_event(db, user.id, "login", request)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(
        select(Session).where(
            Session.token == payload.refresh_token,
            Session.expires_at > datetime.utcnow(),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or not found")

    token_data = {"sub": data["sub"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    session.token = new_refresh
    session.expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(Session.token == payload.refresh_token, Session.super_user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
    await _log_event(db, current_user.id, "logout", request)


@router.get("/me", response_model=SuperUserResponse)
async def get_me(current_user: SuperUser = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=SuperUserResponse)
async def update_me(
    payload: SuperUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    return current_user


@router.post("/change-password", status_code=204)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: SuperUser = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(payload.new_password)
    await _log_event(db, current_user.id, "password_change", request)


@router.get("/verify-email/{token}", status_code=200)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SuperUser).where(SuperUser.email_verification_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.email_verified = True
    user.email_verification_token = None
    user.status = "active"
    return {"message": "Email verified successfully"}
