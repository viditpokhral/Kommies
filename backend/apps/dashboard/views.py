"""
Dashboard Views - Custom UI for website owners
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from .models import Website, Thread, Comment, Subscription, ModerationQueue
import httpx


@login_required
def dashboard_home(request):
    """Main dashboard - overview of all websites"""
    websites = Website.objects.filter(
        super_user__email=request.user.email,
        deleted_at__isnull=True
    ).annotate(
        pending_count=Count('thread__comment', filter=Q(thread__comment__status='pending'))
    )
    
    total_comments = sum(w.total_comments for w in websites)
    total_threads = sum(w.total_threads for w in websites)
    
    # Get subscription info
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
    """Detailed view of a single website"""
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email,
        deleted_at__isnull=True
    )
    
    # Statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    stats = {
        'total_comments': website.total_comments,
        'total_threads': website.total_threads,
        'comments_today': Comment.objects.filter(
            thread__website=website,
            created_at__date=today
        ).count(),
        'comments_week': Comment.objects.filter(
            thread__website=website,
            created_at__date__gte=week_ago
        ).count(),
        'pending': Comment.objects.filter(
            thread__website=website,
            status='pending'
        ).count(),
        'spam': Comment.objects.filter(
            thread__website=website,
            status='spam'
        ).count(),
    }
    
    # Recent threads
    recent_threads = Thread.objects.filter(
        website=website,
        is_deleted=False
    ).order_by('-last_comment_at')[:10]
    
    # Recent comments
    recent_comments = Comment.objects.filter(
        thread__website=website,
        is_deleted=False
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
    """Moderation queue for pending comments"""
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email
    )
    
    pending_comments = Comment.objects.filter(
        thread__website=website,
        status='pending',
        is_deleted=False
    ).select_related('thread').order_by('created_at')
    
    context = {
        'website': website,
        'pending_comments': pending_comments,
    }
    return render(request, 'dashboard/moderation_queue.html', context)


@login_required
def moderate_comment(request, comment_id):
    """Approve/reject a comment - scoped to user's websites only"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    # Security: Only allow moderation of comments from websites owned by this user
    try:
        comment = get_object_or_404(
            Comment.select_related('thread__website__super_user'),
            id=comment_id,
            thread__website__super_user__email=request.user.email,
            thread__website__deleted_at__isnull=True
        )
    except Comment.DoesNotExist:
        return JsonResponse({
            'error': 'Comment not found or you do not have permission to moderate it'
        }, status=403)
    
    action = request.POST.get('action')
    
    if action == 'approve':
        comment.status = 'published'
    elif action == 'spam':
        comment.status = 'spam'
    elif action == 'trash':
        comment.status = 'trash'
    elif action == 'delete':
        comment.is_deleted = True
        comment.status = 'deleted'
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    comment.save()
    
    return JsonResponse({
        'success': True,
        'comment_id': str(comment.id),
        'new_status': comment.status
    })


@login_required
def analytics(request, website_id):
    """Analytics dashboard for a website"""
    website = get_object_or_404(
        Website,
        id=website_id,
        super_user__email=request.user.email
    )
    
    # Last 30 days data
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    daily_comments = Comment.objects.filter(
        thread__website=website,
        created_at__gte=thirty_days_ago
    ).extra(select={'day': 'date(created_at)'}).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Top commenters
    top_commenters = Comment.objects.filter(
        thread__website=website,
        status='published'
    ).values('author_name', 'author_email').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Top threads
    top_threads = Thread.objects.filter(
        website=website
    ).order_by('-comment_count')[:10]
    
    context = {
        'website': website,
        'daily_comments': list(daily_comments),
        'top_commenters': top_commenters,
        'top_threads': top_threads,
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required
def api_test(request, website_id):
    """Test calling FastAPI from Django"""
    website = get_object_or_404(Website, id=website_id)
    
    try:
        # Call FastAPI to get comments
        from django.conf import settings
        response = httpx.get(
            f"{settings.FASTAPI_URL}/api/v1/comments/{website.api_key}/threads/test/comments",
            timeout=10
        )
        data = response.json()
        
        return JsonResponse({
            'success': True,
            'fastapi_response': data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)