"""
backend/apps/dashboard/view_helpers.py

Usage in any view that has a `website` object:

    from .view_helpers import site_ctx
    context = { 'website': website, **site_ctx(website), ...your stuff... }
"""

from django.db.models import Count, Q
from .models import Comment, ModerationReport


def site_ctx(website):
    """
    Returns dict with current_website and pending_count for the sidebar.
    Merge into your view context with **site_ctx(website).
    """
    pending_count = (
        Comment.objects.filter(
            thread__website=website,
            status__in=('spam', 'trash'),
            is_deleted=False,
        ).count()
        +
        ModerationReport.objects.filter(
            status='pending',
            comment__thread__website=website,
            comment__is_deleted=False,
        ).values('comment_id').distinct().count()
    )

    return {
        'current_website': website,
        'pending_count': pending_count,
    }