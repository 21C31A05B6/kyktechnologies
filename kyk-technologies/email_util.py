"""email_util.py — transactional email, with a safe no-server fallback.

Production: set these environment variables and real emails go out over
SMTP (works with SendGrid, Postmark, SES, Gmail's SMTP relay, etc.):

    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM (default "KYK Technologies <no-reply@kyktechnologies.com>")

Demo/dev (no SMTP_HOST set): nothing is sent over the network. Instead
every email is appended to data/outbox.json and printed to the console,
so the application flow can be exercised and inspected without a mail
provider. Swap providers or add templates (e.g. Jinja2 + HTML) without
touching any call site in app.py — they only ever call send_email().
"""

import json
import os
import smtplib
import ssl
from email.message import EmailMessage

import db

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "KYK Technologies <no-reply@kyktechnologies.com>")


def send_email(to, subject, body):
    """Send a plain-text email. Returns True if it was sent (or logged in
    dev mode), False if a real send was attempted and failed."""
    if not SMTP_HOST:
        _log_outbox(to, subject, body)
        print(f"[email:dev-mode] to={to!r} subject={subject!r} (no SMTP_HOST set — logged, not sent)")
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls(context=context)
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[email:error] Failed to send to {to!r}: {exc}")
        return False


def _log_outbox(to, subject, body):
    try:
        db.insert("outbox", {"to": to, "subject": subject, "body": body})
    except Exception:
        pass


# ---------------------------------------------------------------- templates

def send_application_confirmation(to, name, job_title):
    send_email(
        to,
        f"We received your application — {job_title}",
        f"Hi {name},\n\nThanks for applying to the {job_title} role at KYK Technologies. "
        "Our team is reviewing applications and will be in touch if there's a fit.\n\n"
        "— KYK Technologies",
    )


def send_talent_confirmation(to, name):
    send_email(
        to,
        "You're in the KYK talent pool",
        f"Hi {name},\n\nThanks for submitting your profile to KYK Technologies. We'll reach out "
        "directly as soon as a matching role opens with one of our partner organizations.\n\n"
        "— KYK Technologies",
    )


def send_contact_confirmation(to, name):
    send_email(
        to,
        "We received your message",
        f"Hi {name},\n\nThanks for reaching out to KYK Technologies. We reply to every message "
        "within one business day.\n\n— KYK Technologies",
    )


def send_admin_notification(subject, body):
    """Notify every admin account of a new lead/application/message."""
    admins = db.read("admins")
    for admin in admins:
        email = admin.get("email")
        if email:
            send_email(email, subject, body)


_STATUS_LABELS = {
    "reviewing": "Under Review",
    "interview": "Interview Invited",
    "hired":     "Selected",
    "rejected":  "Not Progressing",
}


def send_application_status_update(to, name, job_title, status):
    label = _STATUS_LABELS.get(status)
    if not label:
        return  # don't email for 'new'
    if status == "interview":
        body = (
            f"Hi {name},\n\nGreat news — we'd like to invite you to an interview for the "
            f"{job_title} role at KYK Technologies. Our recruitment team will be in touch "
            f"shortly with scheduling details.\n\n— KYK Technologies"
        )
    elif status == "hired":
        body = (
            f"Hi {name},\n\nWe're delighted to let you know that you've been selected for "
            f"the {job_title} role at KYK Technologies. Our team will reach out with next "
            f"steps very shortly.\n\nWelcome aboard.\n\n— KYK Technologies"
        )
    elif status == "rejected":
        body = (
            f"Hi {name},\n\nThank you for applying for the {job_title} role at KYK Technologies. "
            f"After careful consideration we won't be moving forward with your application at "
            f"this time, but we appreciate you taking the time and wish you all the best.\n\n"
            f"— KYK Technologies"
        )
    else:
        body = (
            f"Hi {name},\n\nYour application for the {job_title} role at KYK Technologies "
            f"is now {label}. We'll be in touch if there are any further updates.\n\n"
            f"— KYK Technologies"
        )
    send_email(to, f"Your application update — {job_title}", body)
