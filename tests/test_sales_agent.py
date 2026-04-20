from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _login_admin(client: TestClient) -> None:
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200


def test_sales_agent_invoked_by_orchestrator_and_updates_case(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_sales_1"
    payload = {
        "message_id": mid,
        "subject": "Oferta współpracy — wdrożenie",
        "from_email": "biz@example.com",
        "to_email": "me@example.com",
        "body": "Chcemy wdrożenie. Mamy budżet. Czy możemy umówić call w tym tygodniu?",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    _login_admin(client)
    rows = client.get("/cases?limit=50").json()
    case = next(c for c in rows if c["message_id"] == mid)
    assert case["lead_stage"] is not None
    assert case["recommended_next_action"] is not None
    assert case["sales_notes"] is not None
    assert "SalesAgent" in (case["assigned_agents"] or [])

    evs = client.get(f"/audit/events/{mid}?limit=200").json()["events"]
    actions = {e["action"] for e in evs}
    assert "sales_review_started" in actions
    assert "sales_review_completed" in actions
    assert "sales_decision_recorded" in actions


def test_sales_review_dev_endpoint_with_email_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    _login_admin(client)
    resp = client.post(
        "/sales/review",
        json={
            "message_id": "m_sales_2",
            "subject": "Partnerstwo / współpraca",
            "from_email": "biz@example.com",
            "to_email": "me@example.com",
            "body": "Proponujemy partnerstwo. Mamy budżet.",
            "thread_context": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"]
    assert data["sales_review"]["recommended_next_action"]

