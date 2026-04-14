from __future__ import annotations

import base64
from email.utils import parseaddr
from typing import Any

from app.schemas.email import EmailInput


def _headers_map(message: dict[str, Any]) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", []) or []
    out: dict[str, str] = {}
    for h in headers:
        name = (h.get("name") or "").strip()
        value = (h.get("value") or "").strip()
        if name:
            out[name.lower()] = value
    return out


def _decode_base64url(data: str) -> str:
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data.encode("utf-8") + b"===")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _extract_text_plain(payload: dict[str, Any]) -> str:
    mime_type = (payload.get("mimeType") or "").lower()

    body = payload.get("body") or {}
    data = body.get("data")
    if mime_type == "text/plain" and isinstance(data, str):
        return _decode_base64url(data).strip()

    # multipart
    parts = payload.get("parts") or []
    if isinstance(parts, list):
        for p in parts:
            txt = _extract_text_plain(p)
            if txt:
                return txt
    return ""


def gmail_message_to_email_input(message: dict[str, Any], thread_context: list[str]) -> EmailInput:
    headers = _headers_map(message)
    subject = headers.get("subject")
    from_raw = headers.get("from", "")
    to_raw = headers.get("to", "")

    _, from_email = parseaddr(from_raw)
    _, to_email = parseaddr(to_raw)

    body_text = _extract_text_plain(message.get("payload", {}) or {})
    if not body_text:
        body_text = "(Brak treści text/plain w wiadomości)"

    return EmailInput(
        message_id=message["id"],
        thread_id=message.get("threadId"),
        subject=subject,
        sender=from_email or None,
        recipients=[to_email] if to_email else [],
        body_text=body_text,
        thread_context=thread_context,
    )


def thread_to_context(thread: dict[str, Any], limit: int = 5) -> list[str]:
    """
    Simple thread context: take last N messages' text/plain bodies (excluding empty).
    """

    msgs = thread.get("messages") or []
    if not isinstance(msgs, list):
        return []
    out: list[str] = []
    for m in msgs[-limit:]:
        txt = _extract_text_plain(m.get("payload", {}) or {})
        if txt:
            out.append(txt)
    return out

