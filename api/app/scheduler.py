"""
Daily Analytics Scheduler
─────────────────────────
Runs at midnight to snapshot WebsiteStat and DailyUsage for all active websites.
Uses APScheduler with AsyncIOScheduler — no separate worker process needed.

Install: pip install apscheduler
"""

import logging
from datetime import date, datetime
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models import Website, Comment, Thread, DailyUsage, WebsiteStat

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def record_website_stats():
    """
    Snapshot per-website comment stats for yesterday.
    Runs at 00:05 daily (slight offset so all day's data is committed).
    Upserts into analytics.website_stats — safe to re-run.
    """
    target_date = date.today()
    logger.info(f"[Analytics] Recording website stats for {target_date}")

    async with AsyncSessionLocal() as db:
        try:
            # Get all active websites
            result = await db.execute(
                select(Website).where(Website.deleted_at.is_(None), Website.status == "active")
            )
            websites = result.scalars().all()

            for website in websites:
                # Total comments (published)
                total_comments = await db.scalar(
                    select(func.count()).select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        Comment.status == "published",
                        Comment.is_deleted == False,
                    )
                ) or 0

                # Spam comments
                spam_comments = await db.scalar(
                    select(func.count()).select_from(Comment)
                    .join(Thread, Thread.id == Comment.thread_id)
                    .where(
                        Thread.website_id == website.id,
                        Comment.status == "spam",
                    )
                ) or 0

                # Unique commenters (by email + name combo)
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

                # Total threads
                total_threads = await db.scalar(
                    select(func.count()).select_from(Thread)
                    .where(Thread.website_id == website.id, Thread.is_deleted == False)
                ) or 0

                # Active threads (commented on in last 30 days)
                active_threads = await db.scalar(
                    select(func.count()).select_from(Thread)
                    .where(
                        Thread.website_id == website.id,
                        Thread.is_deleted == False,
                        Thread.last_comment_at >= datetime.utcnow().replace(
                            hour=0, minute=0, second=0
                        ),
                    )
                ) or 0

                # Upsert into website_stats
                stmt = pg_insert(WebsiteStat).values(
                    website_id=website.id,
                    stat_date=target_date,
                    total_comments=total_comments,
                    approved_comments=total_comments,  # all published = approved
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
    """
    Snapshot per-user API usage for today.
    Currently records a baseline row — extend this once request
    counting middleware is added.
    """
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
                # Get all websites for this user
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


def start_scheduler():
    """Register jobs and start the scheduler."""

    # Record website stats at 00:05 every day
    scheduler.add_job(
        record_website_stats,
        CronTrigger(hour=0, minute=5),
        id="website_stats",
        name="Record daily website stats",
        replace_existing=True,
    )

    # Ensure daily usage rows exist at 00:01
    scheduler.add_job(
        record_daily_usage,
        CronTrigger(hour=0, minute=1),
        id="daily_usage",
        name="Record daily usage baseline",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[Scheduler] Started — website_stats at 00:05, daily_usage at 00:01")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] Stopped")
