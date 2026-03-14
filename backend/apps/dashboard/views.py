"""
Dashboard Views - Custom UI for website owners
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import Website, Thread, Comment, Subscription, ModerationQueue, ModerationReport
import httpx


@login_required
def dashboard_home(request):
    websites = Website.objects.filter(
        super_user__email=request.user.email,
        deleted_at__isnull=True
    ).annotate(
        flagged_count=Count('thread__comment', filter=Q(
            thread__comment__is_deleted=False,
            thread__comment__status__in=('spam', 'trash')
        ))
    )

    total_comments = sum(w.total_comments for w in websites)
    total_threads = sum(w.total_threads for w in websites)

    try:
        subscription = Subscription.objects.get(
            super_user__email=request.user.email,
            status='active'
        )
    except Subscription.DoesNotExist:
        subscription = None

    context = {
        'websites': websites,
        'total_comments': total_comments,
        'total_threads': total_threads,
        'subscription': subscription,
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def website_detail(request, website_id):
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email,
        deleted_at__isnull=True
    )

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    stats = {
        'total_comments': website.total_comments,
        'total_threads': website.total_threads,
        'comments_today': Comment.objects.filter(
            thread__website=website,
            created_at__date=today,
            status='published',
            is_deleted=False,
        ).count(),
        'comments_week': Comment.objects.filter(
            thread__website=website,
            created_at__date__gte=week_ago,
            status='published',
            is_deleted=False,
        ).count(),
        'flagged': Comment.objects.filter(
            thread__website=website,
            status__in=('spam', 'trash'),
            is_deleted=False,
        ).count() + ModerationReport.objects.filter(
            status='pending',
            comment__thread__website=website,
            comment__is_deleted=False,
        ).values('comment_id').distinct().count(),
        'spam': Comment.objects.filter(
            thread__website=website,
            status='spam',
        ).count(),
    }

    recent_threads = Thread.objects.filter(
        website=website,
        is_deleted=False
    ).order_by('-last_comment_at')[:10]

    recent_comments = Comment.objects.filter(
        thread__website=website,
        is_deleted=False,
        status='published',
    ).select_related('thread').order_by('-created_at')[:20]

    context = {
        'website': website,
        'stats': stats,
        'recent_threads': recent_threads,
        'recent_comments': recent_comments,
    }
    return render(request, 'dashboard/website_detail.html', context)


@login_required
def moderation_queue(request, website_id):
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email
    )

    # Comments marked spam/trash by moderator
    moderated = Comment.objects.filter(
        thread__website=website,
        status__in=('spam', 'trash'),
        is_deleted=False,
    ).select_related('thread')

    # Comments reported by users that are still published (not yet actioned)
    reported_ids = ModerationReport.objects.filter(
        status='pending',
        comment__thread__website=website,
        comment__status='published',
        comment__is_deleted=False,
    ).values_list('comment_id', flat=True).distinct()

    reported = Comment.objects.filter(
        id__in=reported_ids,
    ).select_related('thread')

    # Merge and deduplicate, most recent first
    from itertools import chain
    seen = set()
    merged = []
    for c in sorted(chain(moderated, reported), key=lambda x: x.created_at, reverse=True):
        if c.id not in seen:
            seen.add(c.id)
            merged.append(c)

    # Attach report count to each comment
    from django.db.models import Count as _Count
    report_counts = dict(
        ModerationReport.objects.filter(comment_id__in=[c.id for c in merged])
        .values('comment_id')
        .annotate(n=_Count('id'))
        .values_list('comment_id', 'n')
    )
    for c in merged:
        c.report_count = report_counts.get(c.id, 0)

    context = {
        'website': website,
        'flagged_comments': merged,
    }
    return render(request, 'dashboard/moderation_queue.html', context)


@login_required
def moderate_comment(request, comment_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    # Fixed: was Comment.select_related(...) — missing .objects
    comment = get_object_or_404(
        Comment.objects.select_related('thread__website__super_user'),
        id=comment_id,
        thread__website__super_user__email=request.user.email,
        thread__website__deleted_at__isnull=True,
        is_deleted=False,
    )

    action = request.POST.get('action')
    valid_actions = ('spam', 'trash', 'delete')

    if action not in valid_actions:
        return JsonResponse({'error': f'Invalid action. Use: {valid_actions}'}, status=400)

    was_published = comment.status == 'published'

    if action == 'delete':
        comment.is_deleted = True
        comment.status = 'deleted'
        from django.utils import timezone as tz
        comment.deleted_at = tz.now()
        comment.deleted_by = 'moderator'
    else:
        comment.status = action

    comment.save()

    # Mark any pending user reports on this comment as reviewed
    ModerationReport.objects.filter(
        comment=comment, status='pending'
    ).update(status='reviewed')

    # Decrement thread comment_count if was published
    if was_published:
        Thread.objects.filter(id=comment.thread_id).update(
            comment_count=max(0, comment.thread.comment_count - 1)
        )

    return JsonResponse({
        'success': True,
        'comment_id': str(comment.id),
        'new_status': comment.status,
    })


@login_required
def analytics(request, website_id):
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email
    )

    thirty_days_ago = timezone.now() - timedelta(days=30)

    daily_comments = (
        Comment.objects
        .filter(thread__website=website, created_at__gte=thirty_days_ago, status='published')
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    top_commenters = (
        Comment.objects
        .filter(thread__website=website, status='published', is_deleted=False)
        .values('author_name', 'author_email')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    top_threads = (
        Thread.objects
        .filter(website=website, is_deleted=False)
        .order_by('-comment_count')[:10]
    )

    # Spam rate
    total = Comment.objects.filter(thread__website=website).count() or 1
    spam_count = Comment.objects.filter(thread__website=website, status='spam').count()
    spam_rate = round((spam_count / total) * 100, 1)

    context = {
        'website': website,
        'daily_comments': list(daily_comments),
        'top_commenters': top_commenters,
        'top_threads': top_threads,
        'spam_rate': spam_rate,
        'total_comments': website.total_comments,
        'spam_count': spam_count,
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required
def api_test(request, website_id):
    website = get_object_or_404(Website, id=website_id)
    try:
        from django.conf import settings
        response = httpx.get(
            f"{settings.FASTAPI_URL}/api/v1/comments/{website.api_key}/threads/test/comments",
            timeout=10
        )
        return JsonResponse({'success': True, 'fastapi_response': response.json()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def ban_list(request, website_id):
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email,
        deleted_at__isnull=True,
    )
    from .models import BannedEntity
    bans = BannedEntity.objects.filter(website=website, is_active=True)

    by_type = {
        'email':  bans.filter(entity_type='email'),
        'ip':     bans.filter(entity_type='ip'),
        'domain': bans.filter(entity_type='domain'),
    }

    return render(request, 'dashboard/bans.html', {
        'website': website,
        'bans': bans,
        'by_type': by_type,
        'total': bans.count(),
    })


@login_required
def ban_remove(request, website_id, ban_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    from .models import BannedEntity
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email,
        deleted_at__isnull=True,
    )
    ban = get_object_or_404(BannedEntity, id=ban_id, website=website)
    ban.is_active = False
    ban.save()
    return JsonResponse({'success': True})