from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _login_admin(client: TestClient) -> None:
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200


def test_professor_agent_invoked_by_orchestrator_and_updates_case(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_prof_1"
    payload = {
        "message_id": mid,
        "subject": "Wdrożenie integracji API — partnerstwo",
        "from_email": "biz@example.com",
        "to_email": "me@example.com",
        "body": "Chcemy wdrożyć integrację API i omówić partnerstwo. Potrzebujemy planu i ryzyk.",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    _login_admin(client)
    rows = client.get("/cases?limit=50").json()
    case = next(c for c in rows if c["message_id"] == mid)
    assert case["expert_summary"] is not None
    assert isinstance(case["key_risks"], list)
    assert isinstance(case["key_questions"], list)
    assert case["recommended_expert_next_step"] is not None
    assert "ProfessorAgent" in (case["assigned_agents"] or [])

    evs = client.get(f"/audit/events/{mid}?limit=200").json()["events"]
    actions = {e["action"] for e in evs}
    assert "expert_review_started" in actions
    assert "expert_review_completed" in actions
    assert "expert_notes_recorded" in actions


def test_professor_review_dev_endpoint_with_email_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    _login_admin(client)
    resp = client.post(
        "/professor/review",
        json={
            "message_id": "m_prof_2",
            "subject": "Strategiczne wdrożenie",
            "from_email": "biz@example.com",
            "to_email": "me@example.com",
            "body": "Chcemy strategiczne wdrożenie. Jakie ryzyka i pytania powinniśmy zadać?",
            "thread_context": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"]
    assert data["professor_review"]["expert_summary"]
    assert data["professor_review"]["recommended_expert_next_step"]

