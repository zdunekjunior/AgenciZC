from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_pending_list_approve_reject_flow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """
    End-to-end dev flow (in-memory):
    create draft via /gmail/analyze-and-create-draft -> appears in /drafts/pending -> approve/reject change status.
    """

    from app.api.routes.gmail import get_gmail_service, get_orchestrator
    from app.api.routes.drafts import get_draft_service
    from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
    from app.schemas.email import AgentResult

    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()

    # Use a fresh repo/service per test.
    class FreshDraftService:
        def __init__(self) -> None:
            from app.drafts.repository import InMemoryDraftRepository
            from app.drafts.service import DraftApprovalService

            self._svc = DraftApprovalService(repo=InMemoryDraftRepository())

        def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
            return getattr(self._svc, name)

    fresh = FreshDraftService()
    app.dependency_overrides[get_draft_service] = lambda: fresh

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
                recipients=["me@example.com"],
                body_text="Chcemy wysłać ofertę współpracy.",
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            assert draft_reply.strip()
            return "d_1"

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            return label_names

    class StubOrch:
        def handle_email(self, email):  # type: ignore[no-untyped-def]
            return AgentResult(
                category=Category.partnership,
                priority=Priority.medium,
                summary="s",
                needs_human_approval=False,
                recommended_action=RecommendedAction.draft_for_review,
                draft_reply="Draft body",
                reasoning_notes="n",
                suggested_tool=SuggestedTool.none,
                confidence=0.9,
            )

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_orchestrator] = lambda: StubOrch()

    client = TestClient(app)
    assert client.post("/admin/login", json={"password": "pw"}).status_code == 200

    # Create draft (registers pending_review)
    resp = client.post("/gmail/analyze-and-create-draft", json={"message_id": "m1"})
    assert resp.status_code == 200
    assert resp.json()["draft"]["draft_id"] == "d_1"

    pending = client.get("/drafts/pending")
    assert pending.status_code == 200
    drafts = pending.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["draft_id"] == "d_1"
    assert drafts[0]["status"] == "pending_review"

    approved = client.post("/drafts/d_1/approve")
    assert approved.status_code == 200
    assert approved.json()["draft"]["status"] == "approved"

    # After approve, it should disappear from pending.
    pending2 = client.get("/drafts/pending").json()["drafts"]
    assert pending2 == []

    # Reject unknown -> 404
    rej404 = client.post("/drafts/does-not-exist/reject")
    assert rej404.status_code == 404

