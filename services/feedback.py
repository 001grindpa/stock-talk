import os
import re
import smtplib
import threading
import time
from email.message import EmailMessage
from typing import Any, Tuple
import httpx

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# In-memory rate limiting: max 5 requests per hour per IP
_ip_records: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    with _rate_limit_lock:
        timestamps = _ip_records.get(ip, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]
        if len(valid_timestamps) >= RATE_LIMIT_MAX:
            _ip_records[ip] = valid_timestamps
            return False
        valid_timestamps.append(now)
        _ip_records[ip] = valid_timestamps
        return True


def normalize_handle(handle: str | None) -> str:
    if not handle:
        return ""
    cleaned = handle.strip()
    if not cleaned:
        return ""
    # Normalize to a single leading @
    return "@" + cleaned.lstrip("@")


def validate_feedback_input(data: dict[str, Any]) -> Tuple[dict[str, str] | None, str | None]:
    if not isinstance(data, dict):
        return None, "Invalid request body"

    raw_email = data.get("email")
    raw_handle = data.get("handle")
    raw_message = data.get("message")

    if not raw_email or not isinstance(raw_email, str):
        return None, "Email is required"
    email = raw_email.strip()
    if len(email) > 254 or not EMAIL_REGEX.match(email):
        return None, "Please enter a valid email address"

    handle = ""
    if raw_handle is not None:
        if not isinstance(raw_handle, str):
            return None, "Handle must be a string"
        handle = normalize_handle(raw_handle)
        if len(handle) > 60:
            return None, "X handle is too long"

    if not raw_message or not isinstance(raw_message, str):
        return None, "Message is required"
    message = raw_message.strip()
    if len(message) < 10:
        return None, "Message must be at least 10 characters"
    if len(message) > 2000:
        return None, "Message must not exceed 2000 characters"

    return {"email": email, "handle": handle, "message": message}, None


def send_via_resend(
    resend_api_key: str,
    feedback_to: str,
    email_from: str,
    subject: str,
    body: str,
    reply_to: str,
) -> Tuple[bool, str]:
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": email_from,
            "to": [feedback_to],
            "subject": subject,
            "text": body,
            "reply_to": reply_to,
        }
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.is_success:
            return True, "Feedback sent successfully"
        return False, f"Resend API error: {response.text}"
    except Exception as e:
        return False, f"Resend request failed: {str(e)}"


def send_via_smtp(
    feedback_to: str,
    subject: str,
    body: str,
    reply_to: str,
) -> Tuple[bool, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "stocktalkdapp@gmail.com")

    if not smtp_host or not smtp_user or not smtp_password:
        return False, "SMTP configuration is incomplete in environment variables"

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 587

    # Note: Gmail requires an App Password (generated in Google Account security settings), not the account login password.
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = feedback_to
    msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, "Feedback sent successfully"
    except Exception as e:
        return False, f"SMTP delivery error: {str(e)}"


def send_feedback(data: dict[str, Any], remote_addr: str) -> Tuple[dict[str, Any], int]:
    # 1. Rate limit check
    ip = remote_addr or "127.0.0.1"
    if not check_rate_limit(ip):
        return {
            "error": "Rate limit exceeded. You can submit at most 5 feedback messages per hour."
        }, 429

    # 2. Input validation
    validated, error_msg = validate_feedback_input(data)
    if error_msg or not validated:
        return {"error": error_msg or "Validation failed"}, 400

    email = validated["email"]
    handle = validated["handle"]
    message = validated["message"]

    feedback_to = os.getenv("FEEDBACK_TO", "stocktalkdapp@gmail.com")
    subject = f"[Stocktalk feedback] {email}"
    body = (
        f"From: {email}\n"
        f"X: {handle or '(none)'}\n"
        f"IP: {ip}\n"
        f"Message:\n"
        f"{message}"
    )

    # 3. Transport fallback: Resend if key is configured, else SMTP
    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key:
        smtp_from = os.getenv("SMTP_FROM", "onboarding@resend.dev")
        success, msg = send_via_resend(
            resend_api_key=resend_api_key,
            feedback_to=feedback_to,
            email_from=smtp_from,
            subject=subject,
            body=body,
            reply_to=email,
        )
        if success:
            return {"ok": True, "message": "Feedback submitted successfully"}, 200
        return {"error": f"Failed to deliver feedback: {msg}"}, 502

    # Check SMTP credentials
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_host or not smtp_user or not smtp_password:
        return {
            "error": "Feedback service unavailable: email transport is not configured."
        }, 503

    success, msg = send_via_smtp(
        feedback_to=feedback_to,
        subject=subject,
        body=body,
        reply_to=email,
    )
    if success:
        return {"ok": True, "message": "Feedback submitted successfully"}, 200
    return {"error": f"Failed to deliver feedback: {msg}"}, 502