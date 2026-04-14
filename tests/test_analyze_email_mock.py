from fastapi.testclient import TestClient

from app.main import create_app


def test_analyze_email_mock_mode() -> None:
    app = create_app()
    client = TestClient(app)

    payload = {
        "subject": "Pytanie o ofertę",
        "from_email": "client@example.com",
        "to_email": "me@example.com",
        "body": "Cześć, czy możecie podesłać ofertę i terminy?",
        "thread_context": [],
    }

    resp = client.post("/agent/analyze-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert set(data.keys()) == {
        "category",
        "priority",
        "summary",
        "needs_human_approval",
        "recommended_action",
        "draft_reply",
        "reasoning_notes",
        "suggested_tool",
        "confidence",
    }
    assert data["category"]
    assert data["priority"]
    assert isinstance(data["needs_human_approval"], bool)
    assert data["summary"]
    assert data["recommended_action"]
    assert len(data["draft_reply"]) > 0
    assert 0.0 <= float(data["confidence"]) <= 1.0

