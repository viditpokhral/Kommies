import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text, Numeric, Date, JSON
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.db.session import Base


# ── AUTH SCHEMA ──────────────────────────────────────────────────────────────

class SuperUser(Base):
    __tablename__ = "super_users"
    __table_args__ = {"schema": "auth"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    company_name = Column(String(255))
    phone = Column(String(50))
    status = Column(String(50), default="active")
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255))
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    last_login_at = Column(DateTime)
    last_login_ip = Column(INET)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime)

    sessions = relationship("Session", back_populates="super_user", cascade="all, delete-orphan")
    websites = relationship("Website", back_populates="super_user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="super_user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "auth"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="CASCADE"))
    token = Column(String(255), unique=True, nullable=False)
    ip_address = Column(INET)
    user_agent = Column(Text)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    super_user = relationship("SuperUser", back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auth"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="SET NULL"))
    event_type = Column(String(100), nullable=False)
    ip_address = Column(INET)
    user_agent = Column(Text)
    metadata_ = Column("metadata", JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── BILLING SCHEMA ────────────────────────────────────────────────────────────

class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = {"schema": "billing"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    monthly_price = Column(Numeric(10, 2), nullable=False)
    yearly_price = Column(Numeric(10, 2))
    requests_per_month = Column(Integer, nullable=False)
    max_websites = Column(Integer)
    max_comments_per_thread = Column(Integer)
    features = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = {"schema": "billing"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="CASCADE"))
    plan_id = Column(UUID(as_uuid=True), ForeignKey("billing.plans.id"))
    status = Column(String(50), default="active")
    billing_cycle = Column(String(20), default="monthly")
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    requests_used = Column(Integer, default=0)
    requests_limit = Column(Integer, nullable=False)
    overage_allowed = Column(Boolean, default=False)
    overage_rate = Column(Numeric(10, 4))
    auto_renew = Column(Boolean, default=True)
    trial_ends_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    payment_method = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    super_user = relationship("SuperUser", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = {"schema": "billing"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("billing.subscriptions.id", ondelete="SET NULL"))
    super_user_id = Column(UUID(as_uuid=True), ForeignKey("auth.super_users.id", ondelete="SET NULL"))
    invoice_number = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), default="pending")
    amount = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    requests_included = Column(Integer)
    requests_used = Column(Integer)
    overage_requests = Column(Integer, default=0)
    overage_amount = Column(Numeric(10, 2), default=0)
    stripe_invoice_id = Column(String(255))
    paid_at = Column(DateTime)
    due_date = Column(DateTime)
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
