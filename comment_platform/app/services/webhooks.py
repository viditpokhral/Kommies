"""
Webhook Service
───────────────
Dispatches events to customer-configured webhook URLs.
Signs each payload with HMAC-SHA256 so customers can verify authenticity.

Events fired:
  - comment.created
  - comment.approved
  - comment.spam
  - comment.deleted
  - report.created

Usage:
    from app.services.webhooks import webhook_service
    await webhook_service.fire(
        event_type="comment.created",
        website=website,
        payload={"comment": {...}},
        db=db,
    )
"""

import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import WebhookEvent
from app.models.core_moderation_analytics import Website

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RETRY_DELAYS = [30, 120, 300, 900, 3600]   # seconds: 30s, 2m, 5m, 15m, 1h


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    """HMAC-SHA256 signature — customers verify with their webhook_secret."""
    return "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


class WebhookService:

    async def fire(
        self,
        event_type: str,
        website: Website,
        payload: dict,
        db: AsyncSession,
    ) -> Optional[WebhookEvent]:
        """
        Create a WebhookEvent record and attempt immediate delivery.
        If delivery fails it stays in the DB for retry by the background worker.
        """
        # Only fire if the website has a webhook URL configured
        ns_result = await db.execute(
            select(__import__('app.models', fromlist=['NotificationSettings']).NotificationSettings)
            .where(__import__('app.models', fromlist=['NotificationSettings']).NotificationSettings.website_id == website.id)
        )
        ns = ns_result.scalar_one_or_none()
        webhook_url = ns.webhook_url if ns else None
        webhook_secret = ns.webhook_secret if ns else None

        if not webhook_url:
            return None

        event = WebhookEvent(
            website_id=website.id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        db.add(event)
        await db.flush()

        # Attempt immediate delivery (non-blocking — don't fail the request)
        asyncio.create_task(
            self._deliver(event.id, webhook_url, webhook_secret, payload, event_type)
        )
        return event

    async def _deliver(
        self,
        event_id: UUID,
        url: str,
        secret: Optional[str],
        payload: dict,
        event_type: str,
        attempt: int = 1,
    ) -> bool:
        """
        Attempt HTTP delivery of a webhook. Updates the DB record with result.
        Schedules retry on failure (exponential back-off).
        """
        from app.db.session import AsyncSessionLocal

        body = json.dumps({
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Attempt": str(attempt),
        }
        if secret:
            headers["X-Webhook-Signature"] = _sign_payload(secret, body)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body, headers=headers)

            success = 200 <= response.status_code < 300

            async with AsyncSessionLocal() as db:
                result = await db.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
                event = result.scalar_one_or_none()
                if event:
                    event.attempts = attempt
                    event.last_attempt_at = datetime.utcnow()
                    event.response_status = response.status_code
                    event.response_body = response.text[:1000]

                    if success:
                        event.status = "delivered"
                        event.delivered_at = datetime.utcnow()
                        logger.info(f"Webhook delivered: {event_type} → {url} ({response.status_code})")
                    elif attempt < MAX_ATTEMPTS:
                        delay = RETRY_DELAYS[attempt - 1]
                        event.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                        event.status = "pending"
                        logger.warning(
                            f"Webhook failed (attempt {attempt}): {event_type} → {url} "
                            f"({response.status_code}). Retry in {delay}s"
                        )
                        # Schedule retry
                        asyncio.get_event_loop().call_later(
                            delay,
                            lambda: asyncio.create_task(
                                self._deliver(event_id, url, secret, payload, event_type, attempt + 1)
                            ),
                        )
                    else:
                        event.status = "failed"
                        logger.error(f"Webhook permanently failed after {attempt} attempts: {event_type} → {url}")

                    await db.commit()

            return success

        except Exception as e:
            logger.error(f"Webhook delivery error: {e}")
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
                event = result.scalar_one_or_none()
                if event:
                    event.attempts = attempt
                    event.last_attempt_at = datetime.utcnow()
                    event.response_body = str(e)[:1000]
                    if attempt >= MAX_ATTEMPTS:
                        event.status = "failed"
                    else:
                        delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                        event.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                    await db.commit()
            return False

    # ── TYPED EVENT HELPERS ───────────────────────────────────────────────────

    async def comment_created(self, website: Website, comment, thread, db: AsyncSession):
        await self.fire(
            "comment.created",
            website,
            {
                "comment_id": str(comment.id),
                "thread_id": str(comment.thread_id),
                "thread_identifier": thread.identifier,
                "author_name": comment.author_name,
                "content": comment.content[:500],
                "status": comment.status,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
            },
            db,
        )

    async def comment_approved(self, website: Website, comment, db: AsyncSession):
        await self.fire(
            "comment.approved",
            website,
            {
                "comment_id": str(comment.id),
                "author_name": comment.author_name,
                "content": comment.content[:500],
            },
            db,
        )

    async def comment_spam(self, website: Website, comment, db: AsyncSession):
        await self.fire(
            "comment.spam",
            website,
            {
                "comment_id": str(comment.id),
                "author_name": comment.author_name,
                "spam_score": float(comment.spam_score) if comment.spam_score else None,
            },
            db,
        )

    async def comment_deleted(self, website: Website, comment, db: AsyncSession):
        await self.fire(
            "comment.deleted",
            website,
            {
                "comment_id": str(comment.id),
                "deleted_by": comment.deleted_by,
            },
            db,
        )

    async def report_created(self, website: Website, report, comment, db: AsyncSession):
        await self.fire(
            "report.created",
            website,
            {
                "report_id": str(report.id),
                "comment_id": str(report.comment_id),
                "reason": report.reason,
                "author_name": comment.author_name,
            },
            db,
        )


# Singleton instance
webhook_service = WebhookService()
