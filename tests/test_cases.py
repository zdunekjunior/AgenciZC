from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _login_admin(client: TestClient) -> None:
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200


def test_case_created_on_analyze_email_and_listable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_case_1"
    payload = {
        "message_id": mid,
        "subject": "Oferta współpracy partnerskiej",
        "from_email": "biz@example.com",
        "to_email": "me@example.com",
        "body": "Chcemy porozmawiać o współpracy. Mamy budżet.",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    _login_admin(client)
    cases = client.get("/cases?limit=50")
    assert cases.status_code == 200
    rows = cases.json()
    assert any(c["message_id"] == mid for c in rows)

    case = next(c for c in rows if c["message_id"] == mid)
    assert case["source_type"] == "api"
    assert case["subject"] == payload["subject"]
    assert case["current_status"] in {"analyzed", "research_added", "lead_added", "sales_reviewed", "expert_reviewed"}
    assert "EmailOrchestrator" in (case["assigned_agents"] or [])


def test_case_updated_with_research_and_lead_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_case_2"
    payload = {
        "message_id": mid,
        "subject": "Propozycja współpracy — oferta",
        "from_email": "biz@example.com",
        "to_email": "me@example.com",
        "body": "To oferta współpracy. Chcemy wdrożenie. Budżet jest.",
        "thread_context": [],
    }
    r = client.post("/agent/analyze-email", json=payload)
    assert r.status_code == 200

    _login_admin(client)
    rows = client.get("/cases?limit=50").json()
    case = next(c for c in rows if c["message_id"] == mid)
    # Orchestrator should have routed to ResearchAgent (fallback is low confidence) and lead scoring (keywords).
    assert case["research_summary"] is not None
    assert case["lead_summary"] is not None
    assert any(a in (case["assigned_agents"] or []) for a in ["ResearchAgent", "LeadScoringAgent"])


def test_case_linked_with_draft_id_from_gmail_flow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api.routes.gmail import get_gmail_service

    app = create_app()

    class StubGmail:
        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            return {"id": message_id, "threadId": "t1", "payload": {"headers": []}}

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            from app.schemas.email import EmailInput

            return EmailInput(
                message_id=message_id,
                thread_id="t1",
                subject="Oferta współpracy",
                sender="a@b.com",
                recipients=["c@d.com"],
                body_text="x",
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            assert draft_reply.strip()
            return "d_case_123"

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            return label_names

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()

    client = TestClient(app)
    resp = client.post("/gmail/analyze-and-create-draft", json={"message_id": "m_gmail_case"})
    assert resp.status_code == 200
    assert resp.json()["draft"]["draft_id"] == "d_case_123"

    _login_admin(client)
    rows = client.get("/cases?limit=50").json()
    case = next(c for c in rows if c["message_id"] == "m_gmail_case")
    assert case["source_type"] == "gmail"
    assert "d_case_123" in (case["draft_ids"] or [])


def test_get_case_by_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    mid = "m_case_3"
    payload = {
        "message_id": mid,
        "subject": "Hello",
        "from_email": "a@example.com",
        "to_email": "me@example.com",
        "body": "Hi",
        "thread_context": [],
    }
    assert client.post("/agent/analyze-email", json=payload).status_code == 200

    _login_admin(client)
    rows = client.get("/cases?limit=50").json()
    case = next(c for c in rows if c["message_id"] == mid)

    got = client.get(f"/cases/{case['case_id']}")
    assert got.status_code == 200
    assert got.json()["case_id"] == case["case_id"]

