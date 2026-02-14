"""
Django Admin - Beautiful interface for managing Comment Platform
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from .models import SuperUser, Website, Thread, Comment, Plan, Subscription, ModerationQueue


# ── ADMIN FILTERS ─────────────────────────────────────────────────────────────

class ActiveFilter(admin.SimpleListFilter):
    title = 'Active Status'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Active'),
            ('no', 'Inactive'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(deleted_at__isnull=True, status='active')
        if self.value() == 'no':
            return queryset.filter(Q(deleted_at__isnull=False) | ~Q(status='active'))


# ── INLINE ADMINS ─────────────────────────────────────────────────────────────

class WebsiteInline(admin.TabularInline):
    model = Website
    extra = 0
    fields = ['name', 'domain', 'status', 'total_comments', 'created_at']
    readonly_fields = ['total_comments', 'created_at']
    can_delete = False
    max_num = 5


class ThreadInline(admin.TabularInline):
    model = Thread
    extra = 0
    fields = ['identifier', 'title', 'comment_count', 'status']
    readonly_fields = ['comment_count']
    can_delete = False
    max_num = 10


# ── MAIN ADMINS ───────────────────────────────────────────────────────────────

@admin.register(SuperUser)
class SuperUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'company_name', 'status_badge', 'email_verified_badge', 'website_count', 'created_at']
    list_filter = ['status', 'email_verified', 'created_at']
    search_fields = ['email', 'full_name', 'company_name']
    readonly_fields = ['id', 'password_hash', 'created_at', 'updated_at']
    inlines = [WebsiteInline]
    
    fieldsets = (
        ('Account Info', {
            'fields': ('email', 'full_name', 'company_name', 'phone')
        }),
        ('Status', {
            'fields': ('status', 'email_verified')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {'active': 'green', 'suspended': 'red', 'cancelled': 'gray'}
        color = colors.get(obj.status, 'blue')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 12px; border-radius:12px; font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def email_verified_badge(self, obj):
        if obj.email_verified:
            return format_html('✅')
        return format_html('❌')
    email_verified_badge.short_description = 'Verified'
    
    def website_count(self, obj):
        return Website.objects.filter(super_user=obj, deleted_at__isnull=True).count()
    website_count.short_description = 'Websites'


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'owner_email', 'status_badge', 'total_comments', 'total_threads', 'created_at']
    list_filter = [ActiveFilter, 'status', 'created_at']
    search_fields = ['name', 'domain', 'super_user__email']
    readonly_fields = ['id', 'api_key', 'api_secret', 'total_threads', 'total_comments', 'created_at', 'view_dashboard']
    inlines = [ThreadInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('super_user', 'name', 'domain', 'status')
        }),
        ('API Credentials', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('total_threads', 'total_comments', 'view_dashboard')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def owner_email(self, obj):
        return obj.super_user.email
    owner_email.short_description = 'Owner'
    owner_email.admin_order_field = 'super_user__email'
    
    def status_badge(self, obj):
        colors = {'active': 'green', 'suspended': 'orange', 'deleted': 'red'}
        color = colors.get(obj.status, 'blue')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 12px; border-radius:12px; font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def view_dashboard(self, obj):
        url = reverse('dashboard:website-detail', args=[obj.id])
        return format_html('<a href="{}" class="button">View Dashboard →</a>', url)
    view_dashboard.short_description = 'Actions'


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title_or_identifier', 'website_link', 'status', 'comment_count', 'approved_comment_count', 'created_at']
    list_filter = ['status', 'website', 'created_at']
    search_fields = ['title', 'identifier', 'url']
    readonly_fields = ['id', 'comment_count', 'approved_comment_count', 'last_comment_at']
    
    def title_or_identifier(self, obj):
        return obj.title or obj.identifier
    title_or_identifier.short_description = 'Thread'
    
    def website_link(self, obj):
        url = reverse('admin:dashboard_website_change', args=[obj.website.id])
        return format_html('<a href="{}">{}</a>', url, obj.website.name)
    website_link.short_description = 'Website'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author_name', 'content_preview', 'status_badge', 'website', 'spam_indicator', 'votes_display', 'created_at']
    list_filter = ['status', 'is_deleted', 'created_at']
    search_fields = ['author_name', 'author_email', 'content']
    readonly_fields = ['id', 'spam_score', 'upvotes', 'downvotes', 'created_at']
    actions = ['approve_comments', 'mark_as_spam', 'mark_as_trash', 'delete_selected_comments']
    
    fieldsets = (
        ('Author', {
            'fields': ('author_name', 'author_email')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Moderation', {
            'fields': ('status', 'spam_score')
        }),
        ('Engagement', {
            'fields': ('upvotes', 'downvotes')
        }),
        ('Thread', {
            'fields': ('thread', 'parent')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        preview = obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
        return format_html('<span title="{}">{}</span>', obj.content, preview)
    content_preview.short_description = 'Content'
    
    def status_badge(self, obj):
        colors = {
            'published': '#10b981',
            'pending': '#f59e0b',
            'spam': '#ef4444',
            'trash': '#6b7280',
            'deleted': '#1f2937',
        }
        color = colors.get(obj.status, '#3b82f6')
        return format_html(
            '<span style="background:{}; color:white; padding:4px 12px; border-radius:12px; font-size:11px; font-weight:600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def website(self, obj):
        return obj.thread.website.name
    website.short_description = 'Website'
    
    def spam_indicator(self, obj):
        if not obj.spam_score:
            return '-'
        score = float(obj.spam_score)
        if score >= 0.7:
            emoji = '🔴'
            color = '#ef4444'
        elif score >= 0.4:
            emoji = '🟡'
            color = '#f59e0b'
        else:
            emoji = '🟢'
            color = '#10b981'
        return format_html(
            '{} <span style="color:{}">{:.1%}</span>',
            emoji, color, score
        )
    spam_indicator.short_description = 'Spam'
    
    def votes_display(self, obj):
        return format_html('👍 {} · 👎 {}', obj.upvotes, obj.downvotes)
    votes_display.short_description = 'Votes'
    
    # Actions
    def approve_comments(self, request, queryset):
        count = queryset.update(status='published')
        self.message_user(request, f'{count} comment(s) approved.')
    approve_comments.short_description = '✅ Approve selected comments'
    
    def mark_as_spam(self, request, queryset):
        count = queryset.update(status='spam')
        self.message_user(request, f'{count} comment(s) marked as spam.')
    mark_as_spam.short_description = '🚫 Mark as spam'
    
    def mark_as_trash(self, request, queryset):
        count = queryset.update(status='trash')
        self.message_user(request, f'{count} comment(s) moved to trash.')
    mark_as_trash.short_description = '🗑️ Move to trash'
    
    def delete_selected_comments(self, request, queryset):
        count = queryset.update(is_deleted=True, status='deleted')
        self.message_user(request, f'{count} comment(s) deleted.')
    delete_selected_comments.short_description = '❌ Delete permanently'


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_display', 'requests_per_month', 'is_active', 'subscriber_count']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    
    def price_display(self, obj):
        return f'${obj.monthly_price}/mo · ${obj.yearly_price}/yr'
    price_display.short_description = 'Pricing'
    
    def subscriber_count(self, obj):
        count = Subscription.objects.filter(plan=obj, status='active').count()
        return format_html('<strong>{}</strong> subscribers', count)
    subscriber_count.short_description = 'Subscribers'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'plan', 'status_badge', 'usage_bar', 'period_end', 'created_at']
    list_filter = ['status', 'plan']
    search_fields = ['super_user__email', 'super_user__company_name']
    readonly_fields = ['id']
    
    def user_email(self, obj):
        return obj.super_user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'super_user__email'
    
    def status_badge(self, obj):
        colors = {'active': 'green', 'cancelled': 'red', 'past_due': 'orange'}
        color = colors.get(obj.status, 'blue')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 12px; border-radius:12px; font-size:11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def usage_bar(self, obj):
        pct = obj.usage_percentage()
        if pct >= 90:
            color = '#ef4444'
        elif pct >= 70:
            color = '#f59e0b'
        else:
            color = '#10b981'
        
        return format_html(
            '<div style="width:150px; background:#e5e7eb; border-radius:8px; overflow:hidden; height:20px;">'
            '<div style="width:{}%; background:{}; height:100%;"></div></div>'
            '<span style="font-size:11px; color:#6b7280;">{:,} / {:,} ({}%)</span>',
            min(pct, 100), color,
            obj.requests_used, obj.requests_limit, pct
        )
    usage_bar.short_description = 'Usage'
    
    def period_end(self, obj):
        return obj.current_period_end.strftime('%Y-%m-%d')
    period_end.short_description = 'Renews'


@admin.register(ModerationQueue)
class ModerationQueueAdmin(admin.ModelAdmin):
    list_display = ['comment_preview', 'website', 'reason_display', 'severity_badge', 'status_display', 'created_at']
    list_filter = ['severity', 'reviewed_at', 'created_at']
    search_fields = ['comment__content', 'comment__author_name', 'reason']
    readonly_fields = ['id', 'created_at']
    actions = ['mark_as_reviewed']
    
    def comment_preview(self, obj):
        preview = obj.comment.content[:60] + '...' if len(obj.comment.content) > 60 else obj.comment.content
        return format_html('<strong>{}</strong>: {}', obj.comment.author_name, preview)
    comment_preview.short_description = 'Comment'
    
    def reason_display(self, obj):
        return format_html('<span title="{}">{}</span>', obj.reason, obj.reason[:50])
    reason_display.short_description = 'Reason'
    
    def severity_badge(self, obj):
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'critical': '#991b1b',
        }
        color = colors.get(obj.severity, '#3b82f6')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; border-radius:10px; font-size:10px; font-weight:700;">{}</span>',
            color, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'
    
    def status_display(self, obj):
        if obj.reviewed_at:
            return format_html('✅ Reviewed')
        return format_html('⏳ Pending')
    status_display.short_description = 'Status'
    
    def mark_as_reviewed(self, request, queryset):
        count = queryset.update(reviewed_at=timezone.now())
        self.message_user(request, f'{count} item(s) marked as reviewed.')
    mark_as_reviewed.short_description = '✓ Mark as reviewed'
