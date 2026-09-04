"""
Pluggable transactional email.

Backends
--------
`smtp`     real delivery through SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD.
`console`  writes the message to the application log (local development).
`auto`     (default) uses smtp when SMTP_HOST is set, otherwise console.

Nothing in the app calls smtplib directly -- swap in SES/Resend/SendGrid by adding
a backend here and setting EMAIL_BACKEND.

Environment
-----------
EMAIL_BACKEND   auto | smtp | console
SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, SMTP_STARTTLS (1)
EMAIL_FROM      From address (default: SUPPORT_EMAIL from branding)
APP_BASE_URL    Public URL of the web app, used to build links in emails.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

from qguide.app.branding import BRANDING

log = logging.getLogger("qguide.email")


def app_base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:3000").rstrip("/")


def _backend() -> str:
    b = (os.environ.get("EMAIL_BACKEND", "auto") or "auto").strip().lower()
    if b == "auto":
        return "smtp" if os.environ.get("SMTP_HOST") else "console"
    return b


def is_configured() -> bool:
    """True when real delivery is possible (used to decide whether it is safe to
    surface a reset token in an API response during local development)."""
    return _backend() == "smtp" and bool(os.environ.get("SMTP_HOST"))


def _from_address() -> str:
    return os.environ.get("EMAIL_FROM") or BRANDING.support_email


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send one message. Returns True when handed to a transport (or logged in
    console mode); never raises -- callers must not fail a request on email."""
    backend = _backend()
    if backend == "console":
        log.warning("[email:console] to=%s subject=%s\n%s", to, subject, body)
        return True

    msg = EmailMessage()
    msg["From"] = _from_address()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587") or 587)
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = (os.environ.get("SMTP_STARTTLS", "1") or "1") not in ("0", "false", "False")
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            if use_tls:
                s.starttls()
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        return True
    except Exception as exc:                              # noqa: BLE001
        log.error("email send failed to=%s subject=%s err=%s", to, subject, exc)
        return False


# --------------------------------------------------------------------------- #
# Templates                                                                     #
# --------------------------------------------------------------------------- #
def _footer() -> str:
    return (f"\n\n-- \n{BRANDING.app_name}\n{BRANDING.tagline}\n"
            f"Questions? {BRANDING.support_email}\n")


def send_password_reset(to: str, token: str) -> bool:
    link = f"{app_base_url()}/reset?token={token}"
    subject = f"Reset your {BRANDING.app_name} password"
    body = (
        f"Someone requested a password reset for your {BRANDING.app_name} account.\n\n"
        f"Reset your password (link valid for 30 minutes):\n{link}\n\n"
        "If you did not request this, you can safely ignore this email -- your "
        "password will not change."
        + _footer()
    )
    return send_email(to, subject, body)


def send_welcome(to: str, name: str) -> bool:
    subject = f"Welcome to {BRANDING.app_name}"
    body = (
        f"Hi {name or 'there'},\n\n"
        f"Your {BRANDING.app_name} account is ready. {BRANDING.tagline}.\n\n"
        f"Sign in: {app_base_url()}/login\n\n"
        "Reminder: guide scores and outcome predictions are computational "
        "estimates, not validated laboratory or clinical advice."
        + _footer()
    )
    return send_email(to, subject, body)


def send_collaboration_invite(to: str, inviter: str, project_name: str,
                              role: str, link: str) -> bool:
    subject = f"{inviter} invited you to a {BRANDING.app_name} project"
    body = (
        f"{inviter} added you as {role.lower()} on the project "
        f"\"{project_name}\" in {BRANDING.app_name}.\n\n"
        f"Open the project:\n{link}\n"
        + _footer()
    )
    return send_email(to, subject, body)
