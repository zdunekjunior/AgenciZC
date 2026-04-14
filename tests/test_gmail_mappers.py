from __future__ import annotations

import base64

from app.integrations.gmail.mappers import gmail_message_to_email_input


def _b64url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8").rstrip("=")


def test_gmail_message_to_email_input_maps_fields() -> None:
    msg = {
        "id": "m1",
        "threadId": "t1",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "Test"},
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "To", "value": "Bob <bob@example.com>"},
            ],
            "body": {"data": _b64url("Hello world")},
        },
    }
    email = gmail_message_to_email_input(msg, thread_context=["prev"])
    assert email.message_id == "m1"
    assert email.thread_id == "t1"
    assert email.subject == "Test"
    assert str(email.sender) == "alice@example.com"
    assert [str(x) for x in email.recipients] == ["bob@example.com"]
    assert email.body_text == "Hello world"
    assert email.thread_context == ["prev"]

