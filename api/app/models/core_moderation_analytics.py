import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text, Numeric, Date, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.db.session import Base


# ── CORE SCHEMA ───────────────────────────────────────────────────────────────

class Website(Base):
    __tablename__ = "websites"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False)
    allowed_origins = Column(ARRAY(Text), default=[])
    api_key = Column(String(100), unique=True, nullable=False)
    api_secret = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), default="active")
    settings = Column(JSONB, default={})
    total_threads = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime)

    super_user = relationship("SuperUser", back_populates="websites")
    threads = relationship("Thread", back_populates="website", cascade="all, delete-orphan")
    notification_settings = relationship("NotificationSettings", back_populates="website", uselist=False)


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (
        UniqueConstraint("website_id", "identifier"),
        {"schema": "core"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    identifier = Column(String(500), nullable=False)
    title = Column(String(500))
    url = Column(Text)
    status = Column(String(50), default="open")
    comment_count = Column(Integer, default=0)
    approved_comment_count = Column(Integer, default=0)
    last_comment_at = Column(DateTime)
    is_deleted = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="threads")
    comments = relationship("Comment", back_populates="thread", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("core.threads.id", ondelete="CASCADE"))
    parent_id = Column(UUID(as_uuid=True), ForeignKey("core.comments.id", ondelete="CASCADE"))
    author_name = Column(String(255), nullable=False)
    author_email = Column(String(255))
    author_website = Column(String(500))
    author_ip = Column(INET)
    author_user_agent = Column(Text)
    author_identifier = Column(String(255))
    content = Column(Text, nullable=False)
    content_html = Column(Text)
    status = Column(String(50), default="pending")
    spam_score = Column(Numeric(5, 4))
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime)
    edit_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    deleted_by = Column(String(50))
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("Thread", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent")
    votes = relationship("CommentVote", back_populates="comment", cascade="all, delete-orphan")
    history = relationship("CommentHistory", back_populates="comment", cascade="all, delete-orphan")


class CommentHistory(Base):
    __tablename__ = "comment_history"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("core.comments.id", ondelete="CASCADE"))
    content = Column(Text, nullable=False)
    edited_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    comment = relationship("Comment", back_populates="history")


class CommentVote(Base):
    __tablename__ = "comment_votes"
    __table_args__ = (
        UniqueConstraint("comment_id", "voter_identifier"),
        {"schema": "core"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("core.comments.id", ondelete="CASCADE"))
    voter_identifier = Column(String(255), nullable=False)
    vote_type = Column(String(10), nullable=False)
    voter_ip = Column(INET)
    created_at = Column(DateTime, default=datetime.utcnow)

    comment = relationship("Comment", back_populates="votes")


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"), unique=True)
    notify_new_comments = Column(Boolean, default=False)
    notify_replies = Column(Boolean, default=True)
    notify_moderation_needed = Column(Boolean, default=True)
    notify_spam_detected = Column(Boolean, default=False)
    notification_email = Column(String(255))
    webhook_url = Column(Text)
    webhook_secret = Column(String(255))
    slack_webhook_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="notification_settings")


class NotificationQueue(Base):
    __tablename__ = "notification_queue"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    notification_type = Column(String(50), nullable=False)
    recipient_email = Column(String(255))
    subject = Column(String(500))
    body = Column(Text)
    metadata_ = Column("metadata", JSONB, default={})
    status = Column(String(50), default="pending")
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime)
    sent_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(50), default="pending")
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime)
    next_retry_at = Column(DateTime)
    response_status = Column(Integer)
    response_body = Column(Text)
    delivered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── MODERATION SCHEMA ─────────────────────────────────────────────────────────

class ModerationRule(Base):
    __tablename__ = "rules"
    __table_args__ = {"schema": "moderation"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    rule_type = Column(String(50), nullable=False)
    pattern = Column(Text, nullable=False)
    action = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ModerationQueue(Base):
    __tablename__ = "queue"
    __table_args__ = {"schema": "moderation"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("core.comments.id", ondelete="CASCADE"))
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    reason = Column(String(255), nullable=False)
    flagged_by = Column(String(50))
    severity = Column(String(20), default="medium")
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id"))
    reviewed_at = Column(DateTime)
    action_taken = Column(String(50))
    reviewer_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModerationReport(Base):
    __tablename__ = "reports"
    __table_args__ = {"schema": "moderation"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("core.comments.id", ondelete="CASCADE"))
    reporter_identifier = Column(String(255))
    reporter_email = Column(String(255))
    reason = Column(String(50), nullable=False)
    description = Column(Text)
    reporter_ip = Column(INET)
    status = Column(String(50), default="pending")
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class BannedEntity(Base):
    __tablename__ = "banned_entities"
    __table_args__ = (
        UniqueConstraint("website_id", "entity_type", "entity_value"),
        {"schema": "moderation"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    entity_type = Column(String(50), nullable=False)
    entity_value = Column(Text, nullable=False)
    reason = Column(Text)
    banned_by = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id"))
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── ANALYTICS SCHEMA ──────────────────────────────────────────────────────────

class ApiRequest(Base):
    __tablename__ = "api_requests"
    __table_args__ = {"schema": "analytics"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="CASCADE"))
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    ip_address = Column(INET)
    user_agent = Column(Text)
    request_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("super_user_id", "website_id", "usage_date"),
        {"schema": "analytics"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="CASCADE"))
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    usage_date = Column(Date, nullable=False)
    total_requests = Column(Integer, default=0)
    get_requests = Column(Integer, default=0)
    post_requests = Column(Integer, default=0)
    put_requests = Column(Integer, default=0)
    delete_requests = Column(Integer, default=0)
    avg_response_time_ms = Column(Integer)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WebsiteStat(Base):
    __tablename__ = "website_stats"
    __table_args__ = (
        UniqueConstraint("website_id", "stat_date"),
        {"schema": "analytics"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("core.websites.id", ondelete="CASCADE"))
    stat_date = Column(Date, nullable=False)
    total_comments = Column(Integer, default=0)
    approved_comments = Column(Integer, default=0)
    spam_comments = Column(Integer, default=0)
    unique_commenters = Column(Integer, default=0)
    total_threads = Column(Integer, default=0)
    active_threads = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)