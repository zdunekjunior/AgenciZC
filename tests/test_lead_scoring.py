from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_business_email_gets_lead_scored_and_listed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    # Trigger orchestration via public endpoint (not admin-protected)
    mid = "m_business"
    payload = {
        "message_id": mid,
        "subject": "Propozycja współpracy partnerskiej",
        "from_email": "biz@example.com",
        "to_email": "me@example.com",
        "body": "Chcemy zaproponować partnerstwo. Mamy budżet i chcemy umówić call w tym tygodniu.",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    # Admin login to access /leads and /audit
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200

    lead = client.get(f"/leads/{mid}")
    assert lead.status_code == 200
    data = lead.json()
    assert data["entity_id"] == mid
    assert data["scoring"]["lead_score"] >= 40

    # Audit contains lead_scored
    evs = client.get(f"/audit/events/{mid}?limit=200").json()["events"]
    assert any(e["action"] == "lead_scored" for e in evs)


def test_non_business_email_not_scored(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_nonbiz"
    payload = {
        "message_id": mid,
        "subject": "Problem z logowaniem",
        "from_email": "user@example.com",
        "to_email": "me@example.com",
        "body": "Nie mogę się zalogować, wyskakuje błąd. Proszę o pomoc.",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200
    lead = client.get(f"/leads/{mid}")
    assert lead.status_code == 404

