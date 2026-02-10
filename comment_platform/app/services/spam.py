"""
Spam Detection Service
──────────────────────
Scores each comment 0.0–1.0 for spam likelihood using:
  1. Keyword / regex rules loaded from moderation.rules (DB)
  2. Heuristic signals (link count, caps ratio, repeated chars, etc.)
  3. IP/email/domain ban checks against moderation.banned_entities

A score >= threshold (default 0.7 from system_config) means spam.

Usage:
    from app.services.spam import spam_service
    result = await spam_service.check(comment, website, db)
    # result.score, result.is_spam, result.reasons
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import ModerationRule, BannedEntity
from app.models.core_moderation_analytics import Comment, Website

logger = logging.getLogger(__name__)

DEFAULT_SPAM_THRESHOLD = 0.7


# ── RESULT TYPE ───────────────────────────────────────────────────────────────

@dataclass
class SpamResult:
    score: float                    # 0.0 (clean) to 1.0 (definite spam)
    is_spam: bool
    is_banned: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def suggested_status(self) -> str:
        if self.is_banned:
            return "spam"
        if self.is_spam:
            return "spam"
        if self.score >= 0.4:
            return "pending"   # Borderline — send to moderation queue
        return "published"


# ── HEURISTIC CHECKS ──────────────────────────────────────────────────────────

def _count_urls(text: str) -> int:
    return len(re.findall(r'https?://', text, re.IGNORECASE))


def _caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def _has_repeated_chars(text: str, threshold: int = 5) -> bool:
    return bool(re.search(r'(.)\1{' + str(threshold) + r',}', text))


def _has_phone_pattern(text: str) -> bool:
    return bool(re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', text))


def _has_email_pattern(text: str) -> bool:
    return bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text))


def _compute_heuristic_score(content: str, author_name: str) -> tuple[float, list[str]]:
    """
    Returns (score_contribution, list_of_reasons).
    Score is in 0.0-1.0 range.
    """
    reasons: list[str] = []
    score = 0.0

    url_count = _count_urls(content)
    if url_count >= 5:
        score += 0.5
        reasons.append(f"High link count ({url_count})")
    elif url_count >= 2:
        score += 0.2
        reasons.append(f"Multiple links ({url_count})")

    caps = _caps_ratio(content)
    if caps > 0.7 and len(content) > 20:
        score += 0.3
        reasons.append(f"Excessive caps ({int(caps*100)}%)")

    if _has_repeated_chars(content):
        score += 0.2
        reasons.append("Repeated characters")

    if len(content) < 5:
        score += 0.3
        reasons.append("Suspiciously short content")

    # Phone numbers in comments are often spam
    if _has_phone_pattern(content):
        score += 0.15
        reasons.append("Contains phone number")

    # Email address left in comment body is a spam signal
    if _has_email_pattern(content):
        score += 0.1
        reasons.append("Contains email address in body")

    # Very long author names are sometimes bots
    if len(author_name) > 60:
        score += 0.1
        reasons.append("Unusually long author name")

    return min(score, 1.0), reasons


# ── MAIN SERVICE ─────────────────────────────────────────────────────────────

class SpamService:

    async def check(
        self,
        content: str,
        author_name: str,
        author_email: Optional[str],
        author_ip: Optional[str],
        website: Website,
        db: AsyncSession,
        threshold: float = DEFAULT_SPAM_THRESHOLD,
    ) -> SpamResult:
        reasons: list[str] = []
        total_score = 0.0

        # ── 1. Ban list check ─────────────────────────────────────────────────
        is_banned = await self._check_banned(author_email, author_ip, website.id, db)
        if is_banned:
            return SpamResult(score=1.0, is_spam=True, is_banned=True, reasons=["Entity is banned"])

        # ── 2. Heuristic scoring ──────────────────────────────────────────────
        h_score, h_reasons = _compute_heuristic_score(content, author_name)
        total_score += h_score * 0.5   # Heuristics count for 50% of total score
        reasons.extend(h_reasons)

        # ── 3. Rule-based scoring (from DB) ───────────────────────────────────
        r_score, r_reasons = await self._check_rules(content, author_email, website.id, db)
        total_score += r_score * 0.5   # Rules count for 50%
        reasons.extend(r_reasons)

        total_score = min(total_score, 1.0)
        is_spam = total_score >= threshold

        logger.debug(
            f"Spam check: score={total_score:.2f} is_spam={is_spam} "
            f"reasons={reasons}"
        )

        return SpamResult(score=total_score, is_spam=is_spam, reasons=reasons)

    async def _check_banned(
        self,
        email: Optional[str],
        ip: Optional[str],
        website_id,
        db: AsyncSession,
    ) -> bool:
        from datetime import datetime
        from sqlalchemy import or_

        conditions = []

        if email:
            domain = email.split("@")[-1] if "@" in email else None
            email_cond = (
                BannedEntity.entity_type == "email",
                BannedEntity.entity_value == email,
            )
            conditions.append(
                (BannedEntity.entity_type == "email") & (BannedEntity.entity_value == email)
            )
            if domain:
                conditions.append(
                    (BannedEntity.entity_type == "domain") & (BannedEntity.entity_value == domain)
                )

        if ip:
            conditions.append(
                (BannedEntity.entity_type == "ip") & (BannedEntity.entity_value == ip)
            )

        if not conditions:
            return False

        result = await db.execute(
            select(BannedEntity).where(
                or_(*conditions),
                BannedEntity.is_active == True,
                or_(
                    BannedEntity.website_id == website_id,
                    BannedEntity.website_id.is_(None),  # Global bans
                ),
                or_(
                    BannedEntity.expires_at.is_(None),
                    BannedEntity.expires_at > datetime.utcnow(),
                ),
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _check_rules(
        self,
        content: str,
        author_email: Optional[str],
        website_id,
        db: AsyncSession,
    ) -> tuple[float, list[str]]:
        result = await db.execute(
            select(ModerationRule).where(
                ModerationRule.website_id == website_id,
                ModerationRule.is_active == True,
                ModerationRule.rule_type.in_(["banned_word", "banned_email"]),
            ).order_by(ModerationRule.priority.desc())
        )
        rules = result.scalars().all()

        score = 0.0
        reasons: list[str] = []
        content_lower = content.lower()

        for rule in rules:
            try:
                match = False
                if rule.rule_type == "banned_word":
                    match = bool(re.search(rule.pattern, content_lower, re.IGNORECASE))
                elif rule.rule_type == "banned_email" and author_email:
                    match = bool(re.search(rule.pattern, author_email, re.IGNORECASE))

                if match:
                    if rule.action == "block":
                        score += 0.8
                        reasons.append(f"Matched block rule: {rule.pattern[:30]}")
                    elif rule.action == "flag":
                        score += 0.4
                        reasons.append(f"Matched flag rule: {rule.pattern[:30]}")
                    elif rule.action == "quarantine":
                        score += 0.6
                        reasons.append(f"Matched quarantine rule: {rule.pattern[:30]}")

            except re.error:
                logger.warning(f"Invalid regex in rule {rule.id}: {rule.pattern}")
                continue

        return min(score, 1.0), reasons


# Singleton instance
spam_service = SpamService()
