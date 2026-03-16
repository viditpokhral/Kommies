"""
Dashboard Views - Custom UI for website owners
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import (
    Website, Thread, Comment, Subscription,
    ModerationQueue, ModerationReport, BannedEntity, SiteMember, SuperUser,
)
from .access import admin_required, moderator_required, owner_required, viewer_required
from .view_helpers import site_ctx
import httpx


# ── TENANT VIEWS ──────────────────────────────────────────────────────────────

@login_required
def dashboard_home(request):
    websites = Website.objects.filter(
        super_user__email=request.user.email,
        deleted_at__isnull=True,
    ).annotate(
        pending_count=Count(
            'thread__comment',
            filter=Q(
                thread__comment__is_deleted=False,
                thread__comment__status__in=('spam', 'trash'),
            )
        )
    )

    total_comments = sum(w.total_comments for w in websites)
    total_threads  = sum(w.total_threads  for w in websites)

    try:
        subscription = Subscription.objects.get(
            super_user__email=request.user.email,
            status='active',
        )
    except Subscription.DoesNotExist:
        subscription = None

    first = websites.first()
    context = {
        'websites':        websites,
        'total_comments':  total_comments,
        'total_threads':   total_threads,
        'subscription':    subscription,
        'current_website': first,
        'pending_count':   first.pending_count if first else 0,
    }
    return render(request, 'dashboard/home.html', context)


@login_required
@viewer_required
def website_detail(request, website_id):
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)

    today    = timezone.now().date()
    week_ago = today - timedelta(days=7)

    stats = {
        'total_comments':  website.total_comments,
        'total_threads':   website.total_threads,
        'comments_today':  Comment.objects.filter(
            thread__website=website, created_at__date=today,
            status='published', is_deleted=False,
        ).count(),
        'comments_week':   Comment.objects.filter(
            thread__website=website, created_at__date__gte=week_ago,
            status='published', is_deleted=False,
        ).count(),
        'flagged':
            Comment.objects.filter(
                thread__website=website, status__in=('spam', 'trash'), is_deleted=False,
            ).count()
            + ModerationReport.objects.filter(
                status='pending',
                comment__thread__website=website,
                comment__is_deleted=False,
            ).values('comment_id').distinct().count(),
        'spam': Comment.objects.filter(thread__website=website, status='spam').count(),
    }

    recent_threads  = Thread.objects.filter(
        website=website, is_deleted=False,
    ).order_by('-last_comment_at')[:10]

    recent_comments = Comment.objects.filter(
        thread__website=website, is_deleted=False, status='published',
    ).select_related('thread').order_by('-created_at')[:20]

    context = {
        'website':         website,
        'stats':           stats,
        'recent_threads':  recent_threads,
        'recent_comments': recent_comments,
        **site_ctx(website),
    }
    return render(request, 'dashboard/website_detail.html', context)


@login_required
@moderator_required
def moderation_queue(request, website_id):
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)

    moderated = Comment.objects.filter(
        thread__website=website, status__in=('spam', 'trash'), is_deleted=False,
    ).select_related('thread')

    reported_ids = ModerationReport.objects.filter(
        status='pending',
        comment__thread__website=website,
        comment__status='published',
        comment__is_deleted=False,
    ).values_list('comment_id', flat=True).distinct()

    reported = Comment.objects.filter(id__in=reported_ids).select_related('thread')

    from itertools import chain
    seen, merged = set(), []
    for c in sorted(chain(moderated, reported), key=lambda x: x.created_at, reverse=True):
        if c.id not in seen:
            seen.add(c.id)
            merged.append(c)

    report_counts = dict(
        ModerationReport.objects.filter(comment_id__in=[c.id for c in merged])
        .values('comment_id').annotate(n=Count('id')).values_list('comment_id', 'n')
    )
    for c in merged:
        c.report_count = report_counts.get(c.id, 0)

    context = {
        'website':         website,
        'flagged_comments': merged,
        **site_ctx(website),
    }
    return render(request, 'dashboard/moderation_queue.html', context)


@login_required
@moderator_required
def moderate_comment(request, website_id, comment_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    comment = get_object_or_404(
        Comment.objects.select_related('thread__website'),
        id=comment_id, thread__website_id=website_id, is_deleted=False,
    )

    action = request.POST.get('action')
    if action not in ('spam', 'trash', 'delete'):
        return JsonResponse({'error': 'Invalid action. Use: spam, trash, delete'}, status=400)

    was_published = comment.status == 'published'

    if action == 'delete':
        comment.is_deleted = True
        comment.status     = 'deleted'
        comment.deleted_at = timezone.now()
        comment.deleted_by = 'moderator'
    else:
        comment.status = action
    comment.save()

    ModerationReport.objects.filter(comment=comment, status='pending').update(status='reviewed')

    if was_published:
        Thread.objects.filter(id=comment.thread_id).update(
            comment_count=max(0, comment.thread.comment_count - 1)
        )

    return JsonResponse({'success': True, 'comment_id': str(comment.id), 'new_status': comment.status})


@login_required
@viewer_required
def analytics(request, website_id):
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)

    thirty_days_ago = timezone.now() - timedelta(days=30)

    daily_comments = (
        Comment.objects
        .filter(thread__website=website, created_at__gte=thirty_days_ago, status='published')
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )

    top_commenters = (
        Comment.objects
        .filter(thread__website=website, status='published', is_deleted=False)
        .values('author_name', 'author_email')
        .annotate(count=Count('id')).order_by('-count')[:10]
    )

    top_threads = (
        Thread.objects.filter(website=website, is_deleted=False)
        .order_by('-comment_count')[:10]
    )

    total     = Comment.objects.filter(thread__website=website).count() or 1
    spam_count = Comment.objects.filter(thread__website=website, status='spam').count()
    spam_rate  = round((spam_count / total) * 100, 1)

    context = {
        'website':         website,
        'daily_comments':  list(daily_comments),
        'top_commenters':  top_commenters,
        'top_threads':     top_threads,
        'spam_rate':       spam_rate,
        'total_comments':  website.total_comments,
        'spam_count':      spam_count,
        **site_ctx(website),
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required
@moderator_required
def ban_list(request, website_id):
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)
    bans    = BannedEntity.objects.filter(website=website, is_active=True)
    by_type = {
        'email':  bans.filter(entity_type='email'),
        'ip':     bans.filter(entity_type='ip'),
        'domain': bans.filter(entity_type='domain'),
    }
    context = {
        'website': website,
        'bans':    bans,
        'by_type': by_type,
        'total':   bans.count(),
        **site_ctx(website),
    }
    return render(request, 'dashboard/bans.html', context)


@login_required
@moderator_required
def ban_remove(request, website_id, ban_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)
    ban     = get_object_or_404(BannedEntity, id=ban_id, website=website)
    ban.is_active = False
    ban.save()
    return JsonResponse({'success': True})


@login_required
@owner_required
def members_list(request, website_id):
    website = get_object_or_404(Website, id=website_id, deleted_at__isnull=True)
    members = SiteMember.objects.filter(website=website).select_related('super_user')
    context = {
        'website': website,
        'members': members,
        **site_ctx(website),
    }
    return render(request, 'dashboard/members.html', context)


@login_required
def api_test(request, website_id):
    website = get_object_or_404(Website, id=website_id)
    try:
        from django.conf import settings
        response = httpx.get(
            f"{settings.FASTAPI_URL}/api/v1/comments/{website.api_key}/threads/test/comments",
            timeout=10,
        )
        return JsonResponse({'success': True, 'fastapi_response': response.json()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── ADMIN VIEWS ───────────────────────────────────────────────────────────────

@admin_required
def admin_dashboard(request):
    total_tenants  = SuperUser.objects.filter(deleted_at__isnull=True, is_admin=False).count()
    total_websites = Website.objects.filter(deleted_at__isnull=True).count()
    total_comments = Website.objects.filter(deleted_at__isnull=True).aggregate(
        t=Sum('total_comments'))['t'] or 0
    spam_comments  = Comment.objects.filter(status='spam').count()
    recent_tenants = SuperUser.objects.filter(
        deleted_at__isnull=True, is_admin=False,
    ).order_by('-created_at')[:5]

    context = {
        'total_tenants':  total_tenants,
        'total_websites': total_websites,
        'total_comments': total_comments,
        'spam_comments':  spam_comments,
        'recent_tenants': recent_tenants,
    }
    return render(request, 'dashboard/admin/home.html', context)


@admin_required
def admin_tenants(request):
    status_filter = request.GET.get('status', '')
    tenants = SuperUser.objects.filter(deleted_at__isnull=True, is_admin=False)
    if status_filter:
        tenants = tenants.filter(status=status_filter)
    tenants = tenants.annotate(
        website_count=Count('website', filter=Q(website__deleted_at__isnull=True))
    ).order_by('-created_at')
    context = {'tenants': tenants, 'status_filter': status_filter}
    return render(request, 'dashboard/admin/tenants.html', context)


@admin_required
def admin_tenant_detail(request, user_id):
    tenant   = get_object_or_404(SuperUser, id=user_id, deleted_at__isnull=True)
    websites = Website.objects.filter(super_user=tenant, deleted_at__isnull=True).order_by('-created_at')
    context  = {'tenant': tenant, 'websites': websites}
    return render(request, 'dashboard/admin/tenant_detail.html', context)


@admin_required
def admin_tenant_status(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    tenant     = get_object_or_404(SuperUser, id=user_id, deleted_at__isnull=True)
    new_status = request.POST.get('status')
    if new_status not in ('active', 'suspended'):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    tenant.status = new_status
    tenant.save()
    return JsonResponse({'success': True, 'status': new_status})


@admin_required
def admin_comments(request):
    status_filter = request.GET.get('status', '')
    comments = Comment.objects.filter(is_deleted=False).select_related('thread__website')
    if status_filter:
        comments = comments.filter(status=status_filter)
    comments = comments.order_by('-created_at')[:100]
    context  = {'comments': comments, 'status_filter': status_filter}
    return render(request, 'dashboard/admin/comments.html', context)