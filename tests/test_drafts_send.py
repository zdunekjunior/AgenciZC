from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_send_requires_approved(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api.routes.drafts import get_draft_service, get_gmail_service_optional
    from app.drafts.repository import InMemoryDraftRepository
    from app.drafts.service import DraftApprovalService

    app = create_app()

    svc = DraftApprovalService(repo=InMemoryDraftRepository())
    svc.register_new_draft(draft_id="d1", provider="gmail", draft_body="x")

    app.dependency_overrides[get_draft_service] = lambda: svc
    app.dependency_overrides[get_gmail_service_optional] = lambda: None

    client = TestClient(app)
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200
    resp = client.post("/drafts/d1/send")
    assert resp.status_code == 409
    assert "not approved" in resp.text


def test_send_after_approve_marks_sent_and_sets_sent_at(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api.routes.drafts import get_draft_service, get_gmail_service_optional
    from app.drafts.repository import InMemoryDraftRepository
    from app.drafts.service import DraftApprovalService

    app = create_app()

    svc = DraftApprovalService(repo=InMemoryDraftRepository())
    svc.register_new_draft(draft_id="d1", provider="gmail", draft_body="hello")
    svc.approve(draft_id="d1")

    class StubGmail:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def send_draft(self, *, draft_id: str):  # type: ignore[no-untyped-def]
            self.calls.append(draft_id)
            return {"id": "m_sent"}

    stub = StubGmail()

    app.dependency_overrides[get_draft_service] = lambda: svc
    app.dependency_overrides[get_gmail_service_optional] = lambda: stub

    client = TestClient(app)
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200
    resp = client.post("/drafts/d1/send")
    assert resp.status_code == 200
    data = resp.json()["draft"]
    assert data["status"] == "sent"
    assert data["sent_at"] is not None
    assert stub.calls == ["d1"]


def test_cannot_send_twice(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api.routes.drafts import get_draft_service, get_gmail_service_optional
    from app.drafts.repository import InMemoryDraftRepository
    from app.drafts.service import DraftApprovalService

    app = create_app()

    svc = DraftApprovalService(repo=InMemoryDraftRepository())
    svc.register_new_draft(draft_id="d1", provider="gmail", draft_body="hello")
    svc.approve(draft_id="d1")
    svc.mark_sent(draft_id="d1")

    app.dependency_overrides[get_draft_service] = lambda: svc
    app.dependency_overrides[get_gmail_service_optional] = lambda: None

    client = TestClient(app)
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200
    resp = client.post("/drafts/d1/send")
    assert resp.status_code == 409
