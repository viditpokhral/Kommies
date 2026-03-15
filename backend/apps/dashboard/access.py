"""
backend/apps/dashboard/access.py

RBAC decorators for the Django dashboard.

request.user is Django's auth user — NOT the SuperUser unmanaged model.
We bridge via email (same pattern as existing views.py):
    SuperUser.objects.get(email=request.user.email)

Access levels:
    @admin_required          → SuperUser.is_admin = True
    @site_role_required("moderator")  → SiteMember.role >= moderator (or is owner/admin)
    @owner_required          → shorthand for site_role_required("owner")
    @moderator_required      → shorthand for site_role_required("moderator")
    @viewer_required         → shorthand for site_role_required("viewer")
"""

from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect

from .models import SiteMember, SuperUser, Website

ROLE_RANK = {"viewer": 0, "moderator": 1, "owner": 2}


def _get_superuser(request):
    """
    Resolve the SuperUser unmanaged model from the logged-in Django auth user.
    Returns SuperUser or None.
    """
    if not request.user.is_authenticated:
        return None
    try:
        return SuperUser.objects.get(email=request.user.email)
    except SuperUser.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Admin decorator
# ─────────────────────────────────────────────────────────────────────────────

def admin_required(view_func):
    """
    Requires SuperUser.is_admin = True.
    Replaces the inline version in views.py (same logic, extracted here).

        @admin_required
        def admin_dashboard(request): ...
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        su = _get_superuser(request)
        if not su or not su.is_admin:
            return HttpResponseForbidden("Admin access required.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ─────────────────────────────────────────────────────────────────────────────
# Site role decorator
# ─────────────────────────────────────────────────────────────────────────────

def site_role_required(min_role: str, website_kwarg: str = "website_id"):
    """
    Checks the requesting user has at least `min_role` on the website.

    Admins (is_admin=True) bypass the membership check entirely.
    Website owner (Website.super_user_id matches) is treated as owner even
    without a SiteMember row — mirrors the FastAPI require_role behaviour.

        @login_required
        @site_role_required("moderator")
        def moderation_queue(request, website_id): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f'/accounts/login/?next={request.path}')

            su = _get_superuser(request)
            if not su:
                return HttpResponseForbidden("SuperUser account required.")

            # Admins bypass all site checks
            if su.is_admin:
                return view_func(request, *args, **kwargs)

            website_id = kwargs.get(website_kwarg)
            website = get_object_or_404(Website, pk=website_id, deleted_at__isnull=True)

            # Website owner always passes
            if str(website.super_user_id) == str(su.id):
                return view_func(request, *args, **kwargs)

            # Check SiteMember role
            try:
                member = SiteMember.objects.get(website_id=website_id, super_user_id=su.id)
            except SiteMember.DoesNotExist:
                return HttpResponseForbidden("You are not a member of this website.")

            if ROLE_RANK.get(member.role, -1) < ROLE_RANK.get(min_role, 0):
                return HttpResponseForbidden(
                    f"Requires '{min_role}' role or above. Your role: {member.role}"
                )

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# Convenience shorthands
viewer_required    = site_role_required("viewer")
moderator_required = site_role_required("moderator")
owner_required     = site_role_required("owner")