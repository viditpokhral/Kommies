"""
backend/apps/dashboard/context_processors.py

Injects into every template render:
  - user_websites   — QuerySet of websites owned by the logged-in user
  - is_admin        — bool, True if the user is a SuperUser with is_admin=True
"""

from .models import Website, SuperUser


def dashboard_globals(request):
    if not request.user.is_authenticated:
        return {}

    try:
        su = SuperUser.objects.get(email=request.user.email, deleted_at__isnull=True)
        is_admin = su.is_admin
    except SuperUser.DoesNotExist:
        return {}

    if is_admin:
        user_websites = Website.objects.none()
    else:
        user_websites = Website.objects.filter(
            super_user=su,
            deleted_at__isnull=True,
        ).order_by('name')

    return {
        'user_websites': user_websites,
        'is_admin': is_admin,
    }