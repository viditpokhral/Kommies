"""
Email Service
─────────────
Sends all platform emails via SMTP (works with Gmail, SendGrid, Mailgun, etc.)
Uses Jinja2-style templates inline so there are no extra template files needed.

Usage:
    from app.services.email import email_service
    await email_service.send_verification(user, token)
    await email_service.send_new_comment_notification(website, comment, thread)
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
import asyncio
from functools import partial

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── HTML EMAIL TEMPLATES ──────────────────────────────────────────────────────

def _base_template(title: str, body_html: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 0;">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:8px;overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,.08);">
          <!-- Header -->
          <tr>
            <td style="background:#1a1a2e;padding:24px 32px;">
              <span style="color:#ffffff;font-size:20px;font-weight:700;">
                💬 Comment Platform
              </span>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              {body_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background:#f4f4f5;padding:16px 32px;
                       font-size:12px;color:#6b7280;text-align:center;">
              You're receiving this because you have an account on Comment Platform.<br/>
              © 2025 Comment Platform. All rights reserved.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _button(label: str, url: str) -> str:
    return f"""
<a href="{url}" style="display:inline-block;padding:12px 28px;
   background:#1a1a2e;color:#ffffff;text-decoration:none;
   border-radius:6px;font-weight:600;font-size:15px;margin:16px 0;">
  {label}
</a>
"""


def _h1(text: str) -> str:
    return f'<h1 style="margin:0 0 16px;color:#111827;font-size:24px;">{text}</h1>'


def _p(text: str) -> str:
    return f'<p style="margin:0 0 12px;color:#374151;line-height:1.6;">{text}</p>'


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;"/>'


# ── SMTP SENDER ───────────────────────────────────────────────────────────────

class EmailService:
    def __init__(self):
        self.smtp_host: str = getattr(settings, "SMTP_HOST", "smtp.gmail.com")
        self.smtp_port: int = getattr(settings, "SMTP_PORT", 587)
        self.smtp_user: str = getattr(settings, "SMTP_USER", "")
        self.smtp_password: str = getattr(settings, "SMTP_PASSWORD", "")
        self.from_email: str = getattr(settings, "FROM_EMAIL", "noreply@commentplatform.com")
        self.from_name: str = getattr(settings, "FROM_NAME", "Comment Platform")
        self.app_url: str = getattr(settings, "APP_URL", "http://localhost:8000")
        self.enabled: bool = bool(self.smtp_user and self.smtp_password)

    def _send_sync(self, to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
        """Synchronous SMTP send — run in a thread via asyncio."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    async def _send(self, to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
        """Async wrapper — offloads blocking SMTP to thread pool."""
        if not self.enabled:
            logger.warning(f"[EMAIL DISABLED] Would send '{subject}' to {to_email}")
            return False
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self._send_sync, to_email, subject, html_body, text_body),
        )

    # ── TRANSACTIONAL EMAILS ──────────────────────────────────────────────────

    async def send_verification(self, email: str, full_name: Optional[str], token: str) -> bool:
        verify_url = f"{self.app_url}/api/v1/auth/verify-email/{token}"
        name = full_name or "there"
        html = _base_template("Verify your email", (
            _h1("Verify your email address")
            + _p(f"Hi {name}, welcome to Comment Platform!")
            + _p("Click the button below to verify your email and activate your account.")
            + _button("Verify Email", verify_url)
            + _p(f'Or copy this link: <a href="{verify_url}" style="color:#6366f1;">{verify_url}</a>')
            + _divider()
            + _p("This link expires in 24 hours. If you didn't create an account, ignore this email.")
        ))
        return await self._send(email, "Verify your Comment Platform account", html)

    async def send_password_reset(self, email: str, full_name: Optional[str], token: str) -> bool:
        reset_url = f"{self.app_url}/reset-password?token={token}"
        name = full_name or "there"
        html = _base_template("Reset your password", (
            _h1("Reset your password")
            + _p(f"Hi {name}, we received a request to reset your password.")
            + _button("Reset Password", reset_url)
            + _p(f'Or copy this link: <a href="{reset_url}" style="color:#6366f1;">{reset_url}</a>')
            + _divider()
            + _p("This link expires in 1 hour. If you didn't request this, you can safely ignore this email.")
        ))
        return await self._send(email, "Reset your Comment Platform password", html)

    async def send_new_comment_notification(
        self,
        notify_email: str,
        website_name: str,
        author_name: str,
        comment_content: str,
        thread_url: Optional[str],
        moderation_url: str,
    ) -> bool:
        preview = comment_content[:300] + ("..." if len(comment_content) > 300 else "")
        thread_link = f'<a href="{thread_url}" style="color:#6366f1;">{thread_url}</a>' if thread_url else "N/A"
        html = _base_template("New comment on your website", (
            _h1("💬 New comment posted")
            + _p(f"A new comment was posted on <strong>{website_name}</strong>.")
            + f'<table style="width:100%;background:#f9fafb;border-radius:6px;padding:16px;margin:16px 0;">'
            + f'<tr><td><strong>Author:</strong> {author_name}</td></tr>'
            + f'<tr><td><strong>Page:</strong> {thread_link}</td></tr>'
            + f'<tr><td style="padding-top:8px;"><em>"{preview}"</em></td></tr>'
            + '</table>'
            + _button("Review in Dashboard", moderation_url)
        ))
        return await self._send(
            notify_email,
            f"New comment on {website_name}",
            html,
        )

    async def send_moderation_needed(
        self,
        notify_email: str,
        website_name: str,
        pending_count: int,
        moderation_url: str,
    ) -> bool:
        html = _base_template("Comments awaiting moderation", (
            _h1("🔔 Comments need your attention")
            + _p(f"You have <strong>{pending_count} comment(s)</strong> awaiting moderation on <strong>{website_name}</strong>.")
            + _button("Review Now", moderation_url)
        ))
        return await self._send(
            notify_email,
            f"{pending_count} comment(s) awaiting moderation on {website_name}",
            html,
        )

    async def send_reply_notification(
        self,
        author_email: str,
        author_name: str,
        replier_name: str,
        reply_content: str,
        thread_url: Optional[str],
    ) -> bool:
        preview = reply_content[:300] + ("..." if len(reply_content) > 300 else "")
        thread_link = (
            _button("View Reply", thread_url) if thread_url
            else _p("Visit the website to see the reply.")
        )
        html = _base_template("Someone replied to your comment", (
            _h1("💬 You got a reply!")
            + _p(f"Hi {author_name}, <strong>{replier_name}</strong> replied to your comment.")
            + f'<blockquote style="border-left:4px solid #6366f1;margin:16px 0;padding:8px 16px;'
            + f'background:#f5f3ff;color:#374151;border-radius:0 4px 4px 0;">'
            + f'<em>"{preview}"</em></blockquote>'
            + thread_link
            + _divider()
            + _p('<a href="#" style="color:#9ca3af;font-size:12px;">Unsubscribe from reply notifications</a>')
        ))
        return await self._send(
            author_email,
            f"{replier_name} replied to your comment",
            html,
        )

    async def send_subscription_confirmation(
        self,
        email: str,
        full_name: Optional[str],
        plan_name: str,
        billing_cycle: str,
        period_end: str,
    ) -> bool:
        name = full_name or "there"
        html = _base_template("Subscription confirmed", (
            _h1("🎉 You're all set!")
            + _p(f"Hi {name}, your subscription to the <strong>{plan_name}</strong> plan is now active.")
            + f'<table style="width:100%;background:#f9fafb;border-radius:6px;padding:16px;margin:16px 0;">'
            + f'<tr><td><strong>Plan:</strong> {plan_name}</td></tr>'
            + f'<tr><td><strong>Billing:</strong> {billing_cycle.capitalize()}</td></tr>'
            + f'<tr><td><strong>Next renewal:</strong> {period_end}</td></tr>'
            + '</table>'
            + _button("Go to Dashboard", f"{self.app_url}/dashboard")
        ))
        return await self._send(email, f"Welcome to {plan_name} — Comment Platform", html)


# Singleton instance
email_service = EmailService()
