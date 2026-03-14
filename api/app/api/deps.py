from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from fastapi import Request
from app.models import Website

from app.db.session import get_db
from app.core.security import decode_token
from app.models import SuperUser

from app.models.auth_billing import SiteMember
from app.models.core_moderation_analytics import Website
from uuid import UUID as _UUID

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> SuperUser:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(
        select(SuperUser).where(
            SuperUser.id == UUID(user_id),
            SuperUser.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account is {user.status}")

    return user


from fastapi import Request
from app.models import Website

async def check_origin(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    For public comment endpoints keyed by api_key:
    If the website has allowed_origins set, reject requests from unlisted origins.
    Allows requests with no Origin header (server-to-server / curl).
    """
    origin = request.headers.get("origin")
    if not origin:
        return  # non-browser request, allow

    # Extract api_key from path — works for all /{api_key}/... routes
    api_key = request.path_params.get("api_key")
    if not api_key:
        return

    result = await db.execute(
        select(Website).where(Website.api_key == api_key, Website.deleted_at.is_(None))
    )
    website = result.scalar_one_or_none()
    if not website:
        return  # let the endpoint handle 404

    allowed = website.allowed_origins or []
    if not allowed:
        return  # no restrictions configured — open access

    # Normalise: strip trailing slash, lowercase
    def normalise(o):
        return o.rstrip("/").lower()

    if normalise(origin) not in [normalise(o) for o in allowed]:
        raise HTTPException(
            status_code=403,
            detail="Origin not allowed. Add your domain to the website's allowed origins.",
        )


ROLE_HIERARCHY = {"viewer": 0, "moderator": 1, "owner": 2}

def require_role(min_role: str = "viewer"):
    """
    Dependency factory. Use as:
        Depends(require_role("moderator"))
    Returns (website, member) tuple.
    """
    async def _check(
        website_id: _UUID,
        db: AsyncSession = Depends(get_db),
        current_user: SuperUser = Depends(get_current_user),
    ):
        # Check website exists
        w_result = await db.execute(
            select(Website).where(Website.id == website_id, Website.deleted_at.is_(None))
        )
        website = w_result.scalar_one_or_none()
        if not website:
            raise HTTPException(status_code=404, detail="Website not found")

        # Check membership
        m_result = await db.execute(
            select(SiteMember).where(
                SiteMember.website_id == website_id,
                SiteMember.super_user_id == current_user.id,
            )
        )
        member = m_result.scalar_one_or_none()

        # Owner of the website always has access even without a site_member row
        if not member:
            if website.super_user_id == current_user.id:
                # Auto-create owner membership
                member = SiteMember(
                    website_id=website_id,
                    super_user_id=current_user.id,
                    role="owner",
                )
                db.add(member)
                await db.flush()
            else:
                raise HTTPException(status_code=403, detail="Access denied")

        if ROLE_HIERARCHY.get(member.role, -1) < ROLE_HIERARCHY.get(min_role, 0):
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{min_role}' role or higher. Your role: {member.role}"
            )

        return website, member

    return _check
