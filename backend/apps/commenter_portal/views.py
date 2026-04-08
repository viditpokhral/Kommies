"""
Commenter Portal Views
All views proxy to FastAPI commenter endpoints via httpx.
Commenter JWT stored in Django session under 'commenter_token'.
"""
import httpx
from functools import wraps
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods

FASTAPI = settings.FASTAPI_URL


# ── AUTH HELPERS ──────────────────────────────────────────────────────────────

def _auth_headers(request):
    token = request.session.get("commenter_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _refresh_session_user(request):
    """Re-fetch /commenters/me and update session data. Returns user dict or None."""
    try:
        resp = httpx.get(
            f"{FASTAPI}/api/v1/commenters/me",
            headers=_auth_headers(request),
            timeout=10,
        )
        if resp.status_code == 200:
            request.session["commenter"] = resp.json()
            return resp.json()
        return None
    except httpx.RequestError:
        return None


def commenter_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("commenter_token"):
            return redirect("commenter:login")
        return view_func(request, *args, **kwargs)
    return wrapper


def _fastapi_error(resp):
    """Extract a readable error string from a FastAPI error response."""
    try:
        detail = resp.json().get("detail", "Something went wrong.")
        if isinstance(detail, list):
            return detail[0].get("msg", "Validation error.")
        return detail
    except Exception:
        return "Something went wrong."


# ── VIEWS ─────────────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.session.get("commenter_token"):
        return redirect("commenter:profile")

    if request.method == "GET":
        return render(request, "commenter/login.html")

    email    = request.POST.get("email", "").strip()
    password = request.POST.get("password", "").strip()

    if not email or not password:
        return render(request, "commenter/login.html", {
            "error": "Email and password are required.",
            "email": email,
        })

    try:
        resp = httpx.post(
            f"{FASTAPI}/api/v1/commenters/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            request.session["commenter_token"]         = data["access_token"]
            request.session["commenter_refresh_token"] = data.get("refresh_token", "")
            request.session["commenter"]               = data["commenter"]
            next_url = request.GET.get("next", "commenter:profile")
            return redirect(next_url)

        return render(request, "commenter/login.html", {
            "error": _fastapi_error(resp),
            "email": email,
        })

    except httpx.RequestError:
        return render(request, "commenter/login.html", {
            "error": "Could not connect. Please try again shortly.",
            "email": email,
        })


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.session.get("commenter_token"):
        return redirect("commenter:profile")

    if request.method == "GET":
        return render(request, "commenter/register.html")

    display_name = request.POST.get("display_name", "").strip()
    email        = request.POST.get("email", "").strip()
    password     = request.POST.get("password", "").strip()

    # Client-side mirrors of API validation
    if not display_name:
        return render(request, "commenter/register.html", {
            "error": "Display name is required.", "form": request.POST,
        })
    if not email:
        return render(request, "commenter/register.html", {
            "error": "Email is required.", "form": request.POST,
        })
    if len(password) < 8:
        return render(request, "commenter/register.html", {
            "error": "Password must be at least 8 characters.", "form": request.POST,
        })

    # Derive username from display name
    import re
    username = re.sub(r"[^a-z0-9\-_]", "", display_name.lower().replace(" ", "-"))[:30]
    if len(username) < 3:
        username = email.split("@")[0][:30]

    try:
        resp = httpx.post(
            f"{FASTAPI}/api/v1/commenters/register",
            json={
                "display_name": display_name,
                "username":     username,
                "email":        email,
                "password":     password,
            },
            timeout=10,
        )

        if resp.status_code == 201:
            # Auto-login after registration
            login_resp = httpx.post(
                f"{FASTAPI}/api/v1/commenters/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                request.session["commenter_token"]         = data["access_token"]
                request.session["commenter_refresh_token"] = data.get("refresh_token", "")
                request.session["commenter"]               = data["commenter"]
                return redirect("commenter:profile")

            # Login failed (e.g. email not verified) — send to login with note
            return render(request, "commenter/login.html", {
                "info": "Account created! Sign in to continue.",
                "email": email,
            })

        return render(request, "commenter/register.html", {
            "error": _fastapi_error(resp), "form": request.POST,
        })

    except httpx.RequestError:
        return render(request, "commenter/register.html", {
            "error": "Could not connect. Please try again shortly.", "form": request.POST,
        })


def logout_view(request):
    request.session.pop("commenter_token",         None)
    request.session.pop("commenter_refresh_token", None)
    request.session.pop("commenter",               None)
    return redirect("commenter:login")


def verify_email(request, token):
    try:
        resp = httpx.get(
            f"{FASTAPI}/api/v1/commenters/verify-email/{token}",
            timeout=10,
        )
        success = resp.status_code == 200
        error   = None if success else _fastapi_error(resp)
    except httpx.RequestError:
        success = False
        error   = "Could not connect. Please try again."

    return render(request, "commenter/verify_email.html", {
        "success": success, "error": error,
    })


@commenter_required
def profile(request):
    commenter = request.session.get("commenter", {})
    error = success = None

    if request.method == "POST":
        payload = {}
        display_name = request.POST.get("display_name", "").strip()
        bio          = request.POST.get("bio", "").strip()
        avatar_url   = request.POST.get("avatar_url", "").strip()

        if display_name:
            payload["display_name"] = display_name
        if bio is not None:
            payload["bio"] = bio or None
        if avatar_url is not None:
            payload["avatar_url"] = avatar_url or None

        try:
            resp = httpx.patch(
                f"{FASTAPI}/api/v1/commenters/me",
                json=payload,
                headers=_auth_headers(request),
                timeout=10,
            )
            if resp.status_code == 200:
                commenter = resp.json()
                request.session["commenter"] = commenter
                success = "Profile updated."
            elif resp.status_code == 401:
                return redirect("commenter:login")
            else:
                error = _fastapi_error(resp)
        except httpx.RequestError:
            error = "Could not save. Please try again."

    return render(request, "commenter/profile.html", {
        "commenter": commenter,
        "success":   success,
        "error":     error,
    })


@commenter_required
def history(request):
    page      = int(request.GET.get("page", 1))
    page_size = 20
    items     = []
    total     = 0
    pages     = 0
    error     = None

    try:
        resp = httpx.get(
            f"{FASTAPI}/api/v1/commenters/me/comments",
            params={"page": page, "page_size": page_size},
            headers=_auth_headers(request),
            timeout=10,
        )
        if resp.status_code == 200:
            data  = resp.json()
            items = data.get("items", [])
            total = data.get("total", 0)
            pages = data.get("pages", 0)
        elif resp.status_code == 401:
            return redirect("commenter:login")
        else:
            error = _fastapi_error(resp)
    except httpx.RequestError:
        error = "Could not load comments. Please try again."

    return render(request, "commenter/history.html", {
        "commenter": request.session.get("commenter", {}),
        "items":     items,
        "total":     total,
        "page":      page,
        "pages":     pages,
        "page_size": page_size,
        "error":     error,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < pages else None,
    })


@commenter_required
@require_http_methods(["GET", "POST"])
def settings_view(request):
    commenter = request.session.get("commenter", {})
    error = success = None

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Change password ───────────────────────────────────────────────────
        if action == "change_password":
            current  = request.POST.get("current_password", "").strip()
            new_pw   = request.POST.get("new_password", "").strip()
            confirm  = request.POST.get("confirm_password", "").strip()

            if not current or not new_pw:
                error = "All password fields are required."
            elif len(new_pw) < 8:
                error = "New password must be at least 8 characters."
            elif new_pw != confirm:
                error = "Passwords do not match."
            else:
                try:
                    resp = httpx.post(
                        f"{FASTAPI}/api/v1/commenters/change-password",
                        json={"current_password": current, "new_password": new_pw},
                        headers=_auth_headers(request),
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        success = "Password changed successfully."
                    elif resp.status_code == 401:
                        return redirect("commenter:login")
                    else:
                        error = _fastapi_error(resp)
                except httpx.RequestError:
                    error = "Could not connect. Please try again."

        # ── Delete account ────────────────────────────────────────────────────
        elif action == "delete_account":
            confirm_text = request.POST.get("confirm_delete", "").strip()
            if confirm_text != "DELETE":
                error = "Type DELETE to confirm account deletion."
            else:
                try:
                    resp = httpx.delete(
                        f"{FASTAPI}/api/v1/commenters/me",
                        headers=_auth_headers(request),
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        return logout_view(request)
                    elif resp.status_code == 401:
                        return redirect("commenter:login")
                    else:
                        error = _fastapi_error(resp)
                except httpx.RequestError:
                    error = "Could not connect. Please try again."

    return render(request, "commenter/settings.html", {
        "commenter": commenter,
        "success":   success,
        "error":     error,
    })


@require_http_methods(["GET", "POST"])
def forgot_password(request):
    if request.session.get("commenter_token"):
        return redirect("commenter:profile")

    sent  = False
    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            error = "Email is required."
        else:
            try:
                httpx.post(
                    f"{FASTAPI}/api/v1/commenters/forgot-password",
                    json={"email": email},
                    timeout=10,
                )
            except httpx.RequestError:
                pass  # Still show success — never reveal if email exists
            sent = True

    return render(request, "commenter/forgot_password.html", {
        "sent": sent, "error": error,
    })


@require_http_methods(["GET", "POST"])
def reset_password(request, token):
    error = None

    if request.method == "GET":
        return render(request, "commenter/reset_password.html", {"token": token})

    new_pw  = request.POST.get("new_password", "").strip()
    confirm = request.POST.get("confirm_password", "").strip()

    if not new_pw or len(new_pw) < 8:
        error = "Password must be at least 8 characters."
    elif new_pw != confirm:
        error = "Passwords do not match."
    else:
        try:
            resp = httpx.post(
                f"{FASTAPI}/api/v1/commenters/reset-password",
                json={"token": token, "new_password": new_pw},
                timeout=10,
            )
            if resp.status_code == 200:
                return render(request, "commenter/reset_password.html", {
                    "token": token, "success": True,
                })
            error = _fastapi_error(resp)
        except httpx.RequestError:
            error = "Could not connect. Please try again."

    return render(request, "commenter/reset_password.html", {
        "token": token, "error": error,
    })