"""
Django models that mirror the FastAPI PostgreSQL schema.
All models are UNMANAGED (managed=False) - tables exist via bootstrap.sql
"""

from django.db import models # type: ignore
from django.utils import timezone # type: ignore
import uuid


# ── AUTH SCHEMA ───────────────────────────────────────────────────────────────

class SuperUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, default='active')
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'auth"."super_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email


# ── CORE SCHEMA ───────────────────────────────────────────────────────────────

class Website(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    super_user = models.ForeignKey(SuperUser, on_delete=models.CASCADE, db_column='super_user_id')
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    api_key = models.CharField(max_length=100, unique=True)
    api_secret = models.CharField(max_length=100)
    status = models.CharField(max_length=50, default='active')
    total_threads = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'core"."websites'

    def __str__(self):
        return f"{self.name} ({self.domain})"


class Thread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    website = models.ForeignKey(Website, on_delete=models.CASCADE, db_column='website_id')
    identifier = models.CharField(max_length=500)
    title = models.CharField(max_length=500, null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='open')
    comment_count = models.IntegerField(default=0)
    approved_comment_count = models.IntegerField(default=0)
    last_comment_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'core"."threads'

    def __str__(self):
        return self.title or self.identifier


class Comment(models.Model):
    STATUS_CHOICES = [
        ('published', 'Published'),
        ('pending', 'Pending'),
        ('spam', 'Spam'),
        ('trash', 'Trash'),
        ('deleted', 'Deleted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, db_column='thread_id')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, db_column='parent_id')
    author_name = models.CharField(max_length=255)
    author_email = models.EmailField(max_length=255, null=True, blank=True)
    content = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    spam_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'core"."comments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author_name}: {self.content[:50]}..."


# ── BILLING SCHEMA ────────────────────────────────────────────────────────────

class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    requests_per_month = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'billing"."plans'

    def __str__(self):
        return self.name


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    super_user = models.ForeignKey(SuperUser, on_delete=models.CASCADE, db_column='super_user_id')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, db_column='plan_id')
    status = models.CharField(max_length=50, default='active')
    requests_used = models.IntegerField(default=0)
    requests_limit = models.IntegerField()
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)  # ← ADD THIS LINE

    class Meta:
        managed = False
        db_table = 'billing"."subscriptions'

    def usage_percentage(self):
        if self.requests_limit == 0:
            return 0
        return round((self.requests_used / self.requests_limit) * 100, 1)


# ── MODERATION SCHEMA ─────────────────────────────────────────────────────────

class ModerationQueue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, db_column='comment_id')
    website = models.ForeignKey(Website, on_delete=models.CASCADE, db_column='website_id')
    reason = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, default='medium')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'moderation"."queue'
        ordering = ['-created_at']