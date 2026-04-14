from __future__ import annotations

from app.agents.email_agent import EmailAgent
from app.schemas.email import EmailInput


def _email() -> EmailInput:
    return EmailInput(
        message_id="m_test",
        subject="Test",
        sender="client@example.com",
        recipients=["me@example.com"],
        body_text="Cześć, test wiadomości.",
        thread_context=[],
    )


def test_mock_mode_without_api_key_via_http() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    payload = {
        "subject": "Test",
        "from_email": "client@example.com",
        "to_email": "me@example.com",
        "body": "Cześć, test wiadomości.",
        "thread_context": [],
    }
    resp = client.post("/agent/analyze-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]


def test_fallback_when_openai_client_raises_exception() -> None:
    class RaisingClient:
        def create_response_json(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    agent = EmailAgent(client=RaisingClient())  # type: ignore[arg-type]
    result = agent.analyze_email(_email())
    assert result.draft_reply
    assert result.needs_human_approval is True


def test_parsing_recovers_json_from_text_blob() -> None:
    class TextBlobClient:
        def create_response_json(self, **kwargs):  # type: ignore[no-untyped-def]
            # Valid JSON object surrounded by noise.
            return type("R", (), {"output_text": 'OK\n{"category":"other","priority":"medium","summary":"s","needs_human_approval":false,"recommended_action":"draft_for_review","draft_reply":"d","reasoning_notes":"n","suggested_tool":"none","confidence":0.9}\nEND'})()

    agent = EmailAgent(client=TextBlobClient())  # type: ignore[arg-type]
    result = agent.analyze_email(_email())
    assert result.summary == "s"
    assert result.confidence == 0.9


def test_fallback_when_model_returns_invalid_json() -> None:
    class InvalidJsonClient:
        def create_response_json(self, **kwargs):  # type: ignore[no-untyped-def]
            return type("R", (), {"output_text": "NOT JSON AT ALL"})()

    agent = EmailAgent(client=InvalidJsonClient())  # type: ignore[arg-type]
    result = agent.analyze_email(_email())
    assert result.draft_reply
    assert result.needs_human_approval is True

