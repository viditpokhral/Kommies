"""
Email Service
─────────────
Sends all platform emails via SMTP (works with Gmail, SendGrid, Mailgun, etc.)

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
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f3f0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table width="560" cellpadding="0" cellspacing="0" role="presentation"
               style="background:#ffffff;border-radius:10px;overflow:hidden;
                      border:1px solid #e2deda;box-shadow:0 4px 24px rgba(0,0,0,.06);">

          <!-- Header -->
          <tr>
            <td style="background:#111110;padding:22px 32px;">
              <table cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td style="background:#e8673a;border-radius:5px;
                             width:28px;height:28px;text-align:center;
                             vertical-align:middle;">
                    <span style="color:#ffffff;font-size:15px;font-weight:800;
                                 font-family:Georgia,serif;line-height:28px;">K</span>
                  </td>
                  <td style="padding-left:9px;">
                    <span style="color:#f0ede8;font-size:16px;font-weight:700;
                                 letter-spacing:-0.2px;">Kommies</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 32px;">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f4f3f0;padding:18px 32px;
                       border-top:1px solid #e2deda;">
              <p style="margin:0;font-size:12px;color:#b8b2a9;text-align:center;line-height:1.6;">
                You're receiving this because you have an account on Kommies.<br/>
                © 2025 Kommies. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _button(label: str, url: str) -> str:
    return f"""<table cellpadding="0" cellspacing="0" role="presentation" style="margin:20px 0;">
  <tr>
    <td style="background:#e8673a;border-radius:6px;">
      <a href="{url}"
         style="display:inline-block;padding:12px 26px;color:#ffffff;
                text-decoration:none;font-size:14px;font-weight:600;
                letter-spacing:-0.1px;">
        {label}
      </a>
    </td>
  </tr>
</table>"""


def _h1(text: str) -> str:
    return (
        f'<h1 style="margin:0 0 14px;color:#1a1917;font-size:22px;'
        f'font-weight:700;letter-spacing:-0.3px;line-height:1.2;">{text}</h1>'
    )


def _p(text: str) -> str:
    return (
        f'<p style="margin:0 0 12px;color:#4a4640;font-size:14px;'
        f'line-height:1.65;">{text}</p>'
    )


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #e2deda;margin:24px 0;"/>'


def _info_table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr>'
        f'<td style="padding:6px 0;font-size:13px;color:#807b74;width:120px;vertical-align:top;">{k}</td>'
        f'<td style="padding:6px 0;font-size:13px;color:#1a1917;font-weight:500;">{v}</td>'
        f'</tr>'
        for k, v in rows
    )
    return (
        f'<table cellpadding="0" cellspacing="0" role="presentation" '
        f'style="width:100%;background:#f4f3f0;border-radius:8px;'
        f'padding:16px 20px;margin:16px 0;">'
        f'{cells}'
        f'</table>'
    )


def _quote(text: str) -> str:
    return (
        f'<blockquote style="margin:16px 0;padding:12px 16px;'
        f'border-left:3px solid #e8673a;background:#fdf0ea;'
        f'border-radius:0 6px 6px 0;">'
        f'<p style="margin:0;font-size:14px;color:#4a4640;'
        f'line-height:1.6;font-style:italic;">"{text}"</p>'
        f'</blockquote>'
    )


# ── SMTP SENDER ───────────────────────────────────────────────────────────────

class EmailService:
    def __init__(self):
        self.smtp_host: str     = getattr(settings, "SMTP_HOST",     "smtp.gmail.com")
        self.smtp_port: int     = getattr(settings, "SMTP_PORT",     587)
        self.smtp_user: str     = getattr(settings, "SMTP_USER",     "")
        self.smtp_password: str = getattr(settings, "SMTP_PASSWORD", "")
        self.from_email: str    = getattr(settings, "FROM_EMAIL",    "noreply@kommies.io")
        self.from_name: str     = getattr(settings, "FROM_NAME",     "Kommies")
        self.app_url: str       = getattr(settings, "APP_URL",       "http://localhost:8000")
        self.enabled: bool      = bool(self.smtp_user and self.smtp_password)

    def _send_sync(self, to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{self.from_name} <{self.from_email}>"
        msg["To"]      = to_email

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
        html = _base_template("Verify your email — Kommies", (
            _h1("Verify your email address")
            + _p(f"Hi {name}, welcome to Kommies! One quick step to get started:")
            + _button("Verify Email", verify_url)
            + _p(
                f'Or paste this link into your browser:<br/>'
                f'<a href="{verify_url}" style="color:#e8673a;font-size:12px;'
                f'word-break:break-all;">{verify_url}</a>'
            )
            + _divider()
            + _p(
                '<span style="font-size:12px;color:#b8b2a9;">'
                'This link expires in 24 hours. '
                "If you didn't create an account, you can safely ignore this email."
                '</span>'
            )
        ))
        return await self._send(email, "Verify your Kommies account", html)

    async def send_password_reset(self, email: str, full_name: Optional[str], token: str) -> bool:
        reset_url = f"{self.app_url}/reset-password?token={token}"
        name = full_name or "there"
        html = _base_template("Reset your password — Kommies", (
            _h1("Reset your password")
            + _p(f"Hi {name}, we received a request to reset your Kommies password.")
            + _button("Reset Password", reset_url)
            + _p(
                f'Or paste this link into your browser:<br/>'
                f'<a href="{reset_url}" style="color:#e8673a;font-size:12px;'
                f'word-break:break-all;">{reset_url}</a>'
            )
            + _divider()
            + _p(
                '<span style="font-size:12px;color:#b8b2a9;">'
                'This link expires in 1 hour. '
                "If you didn't request a reset, you can safely ignore this email."
                '</span>'
            )
        ))
        return await self._send(email, "Reset your Kommies password", html)

    async def send_new_comment_notification(
        self,
        notify_email: str,
        website_name: str,
        author_name: str,
        comment_content: str,
        thread_url: Optional[str],
        moderation_url: str,
    ) -> bool:
        preview = comment_content[:300] + ("\u2026" if len(comment_content) > 300 else "")
        thread_val = (
            f'<a href="{thread_url}" style="color:#e8673a;">{thread_url}</a>'
            if thread_url else "\u2014"
        )
        html = _base_template(f"New comment on {website_name} \u2014 Kommies", (
            _h1("New comment posted")
            + _p(f"A new comment was posted on <strong>{website_name}</strong>.")
            + _info_table([("Author", author_name), ("Page", thread_val)])
            + _quote(preview)
            + _button("Review in Dashboard", moderation_url)
        ))
        return await self._send(notify_email, f"New comment on {website_name}", html)

    async def send_moderation_needed(
        self,
        notify_email: str,
        website_name: str,
        pending_count: int,
        moderation_url: str,
    ) -> bool:
        s = "s" if pending_count != 1 else ""
        html = _base_template(f"Comments need review \u2014 {website_name}", (
            _h1(f"{pending_count} comment{s} need{'s' if not s else ''} review")
            + _p(
                f"You have <strong>{pending_count} comment{s}</strong> awaiting moderation "
                f"on <strong>{website_name}</strong>."
            )
            + _button("Review Now", moderation_url)
        ))
        return await self._send(
            notify_email,
            f"{pending_count} comment{s} awaiting moderation on {website_name}",
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
        preview = reply_content[:300] + ("\u2026" if len(reply_content) > 300 else "")
        cta = (
            _button("View Reply", thread_url)
            if thread_url
            else _p("Visit the website to see the full reply.")
        )
        html = _base_template(f"{replier_name} replied to your comment \u2014 Kommies", (
            _h1("You got a reply")
            + _p(f"Hi {author_name}, <strong>{replier_name}</strong> replied to your comment.")
            + _quote(preview)
            + cta
            + _divider()
            + _p(
                '<a href="#" style="font-size:12px;color:#b8b2a9;">'
                'Unsubscribe from reply notifications</a>'
            )
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
        html = _base_template(f"You're on {plan_name} \u2014 Kommies", (
            _h1("You're all set!")
            + _p(f"Hi {name}, your <strong>{plan_name}</strong> plan is now active.")
            + _info_table([
                ("Plan",    plan_name),
                ("Billing", billing_cycle.capitalize()),
                ("Renews",  period_end),
            ])
            + _button("Go to Dashboard", f"{self.app_url}/dashboard")
        ))
        return await self._send(email, f"Welcome to {plan_name} \u2014 Kommies", html)


    def send_verification_sync(self, email: str, full_name: Optional[str], verify_url: str) -> bool:
        name = full_name or "there"
        html = _base_template("Verify your email — Kommies", (
            _h1("Verify your email address")
            + _p(f"Hi {name}, welcome to Kommies! One quick step to get started:")
            + _button("Verify Email", verify_url)
            + _p(
                f'Or paste this link into your browser:<br/>'
                f'<a href="{verify_url}" style="color:#e8673a;font-size:12px;'
                f'word-break:break-all;">{verify_url}</a>'
            )
            + _divider()
            + _p(
                '<span style="font-size:12px;color:#b8b2a9;">'
                'This link expires in 24 hours. '
                "If you didn't create an account, you can safely ignore this email."
                '</span>'
            )
        ))
        return self._send_sync(email, "Verify your Kommies account", html)
    

# Singleton instance
email_service = EmailService()