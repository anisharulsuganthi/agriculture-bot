"""
Notification service (Phase 1 - secret handling).

Version 1 had a real Gmail app password committed in source as a fallback
(PROJECT_AUDIT.md §10 S4). Credentials now come only from configuration
(environment / backend/.env, which is git-ignored), and the service degrades
gracefully with a clear message instead of crashing when they are absent.

No credential is ever logged: the logging filter redacts registered secrets.
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

from app.config import settings
from app.logging_config import get_logger, register_secret

logger = get_logger("notification_service")

register_secret(settings.sender_app_password)

NOT_CONFIGURED_MESSAGE = (
    "Email sending is not configured. Set SENDER_EMAIL and EMAIL_APP_PASSWORD "
    "(Gmail app password) in backend/.env to enable notifications."
)


def is_configured() -> bool:
    return bool(settings.sender_email and settings.sender_app_password and settings.email_enabled)


def _send(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    if not settings.email_enabled:
        logger.info("Email disabled by configuration; skipping message to %s", to_email)
        return {"status": "disabled", "message": "Email sending is disabled (EMAIL_ENABLED=false)."}
    if not is_configured():
        logger.warning("Email credentials missing; cannot send to %s", to_email)
        return {"status": "error", "message": NOT_CONFIGURED_MESSAGE}

    try:
        message = MIMEMultipart()
        message["From"] = settings.sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(settings.sender_email, settings.sender_app_password)
            server.sendmail(settings.sender_email, to_email, message.as_string())

        logger.info("Email sent to %s (subject=%s)", to_email, subject)
        return {"status": "success", "message": "Email sent successfully!"}
    except Exception as exc:  # noqa: BLE001 - SMTP can fail in many ways
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return {"status": "error", "message": "Email delivery failed. Check SMTP settings and logs."}


def send_email_alert(to_email: str, message_body: str) -> Dict[str, Any]:
    """Send a climate/disease advisory email."""
    return _send(to_email, "Smart Farm Climate & Disease Alert", message_body)


def send_otp_email(to_email: str, otp: str) -> Dict[str, Any]:
    """Send a password-reset OTP email."""
    body = f"""Hello,

You have requested to reset your password for your Smart Farm account.

Your OTP (One Time Password) is: {otp}

This OTP is valid for {settings.otp_expiry_minutes} minutes. If you did not request this, you can ignore this email safely.

Best regards,
Smart Farm - Agricultural Decision Intelligence System"""
    return _send(to_email, "Smart Farm - Password Reset OTP", body)


def format_alert_message(session_name: str, crop_type: str, recommendations: Dict[str, Any]) -> str:
    """Format recommendations into a readable plain-text advisory."""
    lines = [f"Smart Farm Alert for {crop_type} ({session_name})", ""]

    watering = recommendations.get("watering") or {}
    if watering:
        lines.append(f"Water: {watering.get('recommendation')}")
        lines.append(f"   Reason: {watering.get('reason')}")
        lines.append("")

    fertilizing = recommendations.get("fertilizing") or {}
    if fertilizing:
        lines.append(f"Fertilize: {fertilizing.get('recommendation')}")
        lines.append(f"   Type: {fertilizing.get('fertilizer_type')}")
        lines.append(f"   Reason: {fertilizing.get('reason')}")
        lines.append("")

    disease = recommendations.get("disease_risk") or {}
    if disease.get("risk_level") in {"Medium", "High"}:
        lines.append(f"Disease Risk ({disease.get('risk_level')}): {disease.get('action')}")
        lines.append(f"   Reason: {disease.get('message')}")

    return "\n".join(lines)
