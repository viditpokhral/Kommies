from fastapi import APIRouter
from app.api.v1.endpoints import auth, websites, comments, moderation, billing, analytics

router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(websites.router)
router.include_router(comments.router)
router.include_router(moderation.router)
router.include_router(billing.router)
router.include_router(analytics.router)
