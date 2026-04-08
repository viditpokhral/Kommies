"""
Daily Analytics Scheduler
─────────────────────────
Runs at midnight to snapshot WebsiteStat and DailyUsage for all active websites.
Also sends daily moderation digest emails to website owners with pending items.
"""

import logging
from datetime import date, datetime
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models import Website, Comment, Thread, DailyUsage, WebsiteStat, ModerationReport, ModerationQueue
from app.services.email import email_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def record_website_stats():
    """Snapshot per-website comment stats. Runs at 00:05 daily."""
    target_date = date.today()
    logger.info(f"[Analytics] Recording website stats for {target_date}")

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Website).where(Website.deleted_at.is_(None), Website.status == "active")
            )
            websites = result.scalars().all()

            for website in websites:
                total_comments = await db.scalar(
                    select(func.count()).select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        Comment.status == "published",
                        Comment.is_deleted == False,
                    )
                ) or 0

                spam_comments = await db.scalar(
                    select(func.count()).select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(Thread.website_id == website.id, Comment.status == "spam")
                ) or 0

                unique_commenters = await db.scalar(
                    select(func.count(func.distinct(Comment.author_email)))
                    .select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        Comment.status == "published",
                        Comment.is_deleted == False,
                        Comment.author_email.isnot(None),
                    )
                ) or 0

                total_threads = await db.scalar(
                    select(func.count()).select_from(Thread)
                    .where(Thread.website_id == website.id, Thread.is_deleted == False)
                ) or 0

                active_threads = await db.scalar(
                    select(func.count()).select_from(Thread)
                    .where(
                        Thread.website_id == website.id,
                        Thread.is_deleted == False,
                        Thread.last_comment_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
                    )
                ) or 0

                stmt = pg_insert(WebsiteStat).values(
                    website_id=website.id,
                    stat_date=target_date,
                    total_comments=total_comments,
                    approved_comments=total_comments,
                    spam_comments=spam_comments,
                    unique_commenters=unique_commenters,
                    total_threads=total_threads,
                    active_threads=active_threads,
                    created_at=datetime.utcnow(),
                ).on_conflict_do_update(
                    index_elements=["website_id", "stat_date"],
                    set_={
                        "total_comments": total_comments,
                        "approved_comments": total_comments,
                        "spam_comments": spam_comments,
                        "unique_commenters": unique_commenters,
                        "total_threads": total_threads,
                        "active_threads": active_threads,
                    }
                )
                await db.execute(stmt)

            await db.commit()
            logger.info(f"[Analytics] Recorded stats for {len(websites)} websites")

        except Exception as e:
            await db.rollback()
            logger.error(f"[Analytics] Failed to record website stats: {e}")


async def record_daily_usage():
    """Ensure daily usage rows exist for all active users. Runs at 00:01."""
    target_date = date.today()
    logger.info(f"[Analytics] Recording daily usage for {target_date}")

    async with AsyncSessionLocal() as db:
        try:
            from app.models import SuperUser

            result = await db.execute(
                select(SuperUser).where(SuperUser.deleted_at.is_(None), SuperUser.status == "active")
            )
            users = result.scalars().all()

            for user in users:
                websites_result = await db.execute(
                    select(Website).where(
                        Website.super_user_id == user.id,
                        Website.deleted_at.is_(None),
                    )
                )
                websites = websites_result.scalars().all()

                for website in websites:
                    stmt = pg_insert(DailyUsage).values(
                        super_user_id=user.id,
                        website_id=website.id,
                        usage_date=target_date,
                        total_requests=0,
                        get_requests=0,
                        post_requests=0,
                        error_count=0,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ).on_conflict_do_nothing(
                        index_elements=["super_user_id", "website_id", "usage_date"]
                    )
                    await db.execute(stmt)

            await db.commit()
            logger.info(f"[Analytics] Daily usage rows ensured for {len(users)} users")

        except Exception as e:
            await db.rollback()
            logger.error(f"[Analytics] Failed to record daily usage: {e}")


async def send_moderation_digests():
    """
    Send daily moderation digest to website owners who have pending items.
    Runs at 08:00 — only sends if there are actually pending items.
    """
    logger.info("[Notifications] Sending moderation digest emails")

    async with AsyncSessionLocal() as db:
        try:
            from app.models import SuperUser, NotificationSettings

            # Get all active websites with their owner email + notification settings
            result = await db.execute(
                select(Website).where(
                    Website.deleted_at.is_(None),
                    Website.status == "active",
                )
            )
            websites = result.scalars().all()

            sent = 0
            for website in websites:
                # Check notification settings
                ns_result = await db.execute(
                    select(NotificationSettings)
                    .where(NotificationSettings.website_id == website.id)
                )
                ns = ns_result.scalar_one_or_none()

                # Skip if no notification email or digest not enabled
                if not ns or not ns.notification_email:
                    continue
                if not getattr(ns, "notify_moderation_digest", True):
                    continue

                # Count pending moderation items:
                # spam/trash comments + published comments with pending reports
                spam_count = await db.scalar(
                    select(func.count()).select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        Comment.status.in_(["spam", "trash"]),
                        Comment.is_deleted == False,
                    )
                ) or 0

                reported_count = await db.scalar(
                    select(func.count(func.distinct(ModerationReport.comment_id)))
                    .select_from(ModerationReport)
                    .join(Comment, Comment.id == ModerationReport.comment_id)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        ModerationReport.status == "pending",
                        Comment.is_deleted == False,
                    )
                ) or 0

                pending_count = spam_count + reported_count

                if pending_count == 0:
                    continue  # Nothing to report — skip silently

                moderation_url = f"http://localhost:8001/dashboard/website/{website.id}/moderation/"

                await email_service.send_moderation_needed(
                    notify_email=ns.notification_email,
                    website_name=website.name,
                    pending_count=pending_count,
                    moderation_url=moderation_url,
                )
                sent += 1

            logger.info(f"[Notifications] Sent {sent} moderation digest emails")

        except Exception as e:
            logger.error(f"[Notifications] Failed to send moderation digests: {e}")


def start_scheduler():
    """Register jobs and start the scheduler."""

    scheduler.add_job(
        record_website_stats,
        CronTrigger(hour=0, minute=5),
        id="website_stats",
        name="Record daily website stats",
        replace_existing=True,
    )

    scheduler.add_job(
        record_daily_usage,
        CronTrigger(hour=0, minute=1),
        id="daily_usage",
        name="Record daily usage baseline",
        replace_existing=True,
    )

    scheduler.add_job(
        send_moderation_digests,
        CronTrigger(hour=8, minute=0),
        id="moderation_digest",
        name="Send daily moderation digest emails",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "[Scheduler] Started — "
        "daily_usage at 00:01, website_stats at 00:05, moderation_digest at 08:00"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] Stopped")