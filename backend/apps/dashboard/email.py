"""
Dashboard email service
Sends branded HTML emails from the Django side using Django's own SMTP config.
"""
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ── HTML primitives (mirrors api/app/services/email.py) ──────────────────────

def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f3f0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="560" cellpadding="0" cellspacing="0" role="presentation"
             style="background:#ffffff;border-radius:10px;overflow:hidden;
                    border:1px solid #e2deda;box-shadow:0 4px 24px rgba(0,0,0,.06);">
        <tr>
          <td style="background:#111110;padding:22px 32px;">
            <table cellpadding="0" cellspacing="0" role="presentation"><tr>
              <td style="background:#e8673a;border-radius:5px;width:28px;height:28px;
                         text-align:center;vertical-align:middle;">
                <span style="color:#fff;font-size:15px;font-weight:800;
                             font-family:Georgia,serif;line-height:28px;">K</span>
              </td>
              <td style="padding-left:9px;">
                <span style="color:#f0ede8;font-size:16px;font-weight:700;
                             letter-spacing:-0.2px;">Kommies</span>
              </td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 32px;">{body_html}</td>
        </tr>
        <tr>
          <td style="background:#f4f3f0;padding:18px 32px;border-top:1px solid #e2deda;">
            <p style="margin:0;font-size:12px;color:#b8b2a9;text-align:center;line-height:1.6;">
              You're receiving this because you have an account on Kommies.<br/>
              © 2025 Kommies. All rights reserved.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _h1(text: str) -> str:
    return (f'<h1 style="margin:0 0 14px;color:#1a1917;font-size:22px;'
            f'font-weight:700;letter-spacing:-0.3px;line-height:1.2;">{text}</h1>')


def _p(text: str) -> str:
    return (f'<p style="margin:0 0 12px;color:#4a4640;font-size:14px;'
            f'line-height:1.65;">{text}</p>')


def _button(label: str, url: str) -> str:
    return (f'<table cellpadding="0" cellspacing="0" role="presentation" style="margin:20px 0;">'
            f'<tr><td style="background:#e8673a;border-radius:6px;">'
            f'<a href="{url}" style="display:inline-block;padding:12px 26px;color:#ffffff;'
            f'text-decoration:none;font-size:14px;font-weight:600;">{label}</a>'
            f'</td></tr></table>')


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #e2deda;margin:24px 0;"/>'


# ── Sender ────────────────────────────────────────────────────────────────────

def _send(to_email: str, subject: str, html_body: str, plain_body: str = "") -> bool:
    smtp_host     = getattr(settings, "EMAIL_HOST",          "smtp.gmail.com")
    smtp_port     = getattr(settings, "EMAIL_PORT",          587)
    smtp_user     = getattr(settings, "EMAIL_HOST_USER",     "")
    smtp_password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
    from_email    = getattr(settings, "DEFAULT_FROM_EMAIL",  smtp_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Kommies <{from_email}>"
    msg["To"]      = to_email

    if plain_body:
        msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        logger.info(f"Email sent → {to_email}: {subject}")
        return True
    except Exception as exc:
        logger.error(f"Email failed → {to_email}: {exc}")
        return False


# ── Transactional emails ──────────────────────────────────────────────────────

def send_verification_email(email: str, full_name: Optional[str], verify_url: str) -> bool:
    name = full_name or email
    html = _base_template("Verify your email — Kommies", (
        _h1("Verify your email address")
        + _p(f"Hi {name}, welcome to Kommies! One quick step to get started:")
        + _button("Verify Email", verify_url)
        + _p(f'Or paste this link into your browser:<br/>'
             f'<a href="{verify_url}" style="color:#e8673a;font-size:12px;'
             f'word-break:break-all;">{verify_url}</a>')
        + _divider()
        + _p('<span style="font-size:12px;color:#b8b2a9;">'
             'This link expires in 24 hours. '
             "If you didn't create a Kommies account, you can safely ignore this email."
             '</span>')
    ))
    plain = (f"Hi {name},\n\n"
             f"Verify your Kommies account:\n{verify_url}\n\n"
             f"This link expires in 24 hours.\n\n— The Kommies Team")
    return _send(email, "Verify your Kommies account", html, plain)