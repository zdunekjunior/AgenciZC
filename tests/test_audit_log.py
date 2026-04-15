from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_audit_events_for_draft_lifecycle(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.audit import get_audit_service
    from app.api.routes.drafts import get_draft_service, get_gmail_service_optional
    from app.audit.repository import InMemoryAuditRepository
    from app.audit.service import AuditLogService
    from app.drafts.repository import InMemoryDraftRepository
    from app.drafts.service import DraftApprovalService

    app = create_app()

    audit = AuditLogService(repo=InMemoryAuditRepository())
    drafts = DraftApprovalService(repo=InMemoryDraftRepository())
    drafts.register_new_draft(draft_id="d1", provider="gmail", draft_body="hello")

    class StubGmail:
        def send_draft(self, *, draft_id: str):  # type: ignore[no-untyped-def]
            return {"id": "m_sent"}

    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[get_draft_service] = lambda: drafts
    app.dependency_overrides[get_gmail_service_optional] = lambda: StubGmail()

    client = TestClient(app)

    # approve -> audit
    r1 = client.post("/drafts/d1/approve")
    assert r1.status_code == 200

    # send -> audit
    r2 = client.post("/drafts/d1/send")
    assert r2.status_code == 200
    assert r2.json()["draft"]["status"] == "sent"

    # list all events
    evs = client.get("/audit/events?limit=50").json()["events"]
    actions = [e["action"] for e in evs if e["entity_id"] == "d1"]
    assert "draft_approved" in actions
    assert "draft_sent" in actions

    # list events for entity
    evs2 = client.get("/audit/events/d1?limit=50").json()["events"]
    actions2 = [e["action"] for e in evs2]
    assert "draft_approved" in actions2
    assert "draft_sent" in actions2


def test_audit_event_on_reject(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.audit import get_audit_service
    from app.api.routes.drafts import get_draft_service
    from app.audit.repository import InMemoryAuditRepository
    from app.audit.service import AuditLogService
    from app.drafts.repository import InMemoryDraftRepository
    from app.drafts.service import DraftApprovalService

    app = create_app()

    audit = AuditLogService(repo=InMemoryAuditRepository())
    drafts = DraftApprovalService(repo=InMemoryDraftRepository())
    drafts.register_new_draft(draft_id="d2", provider="gmail", draft_body="hello")

    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[get_draft_service] = lambda: drafts

    client = TestClient(app)

    r = client.post("/drafts/d2/reject")
    assert r.status_code == 200

    evs = client.get("/audit/events/d2?limit=20").json()["events"]
    assert any(e["action"] == "draft_rejected" for e in evs)

