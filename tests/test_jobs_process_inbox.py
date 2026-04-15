from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_process_inbox_skips_already_processed_and_summarizes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.jobs import get_orchestrator, get_gmail_service
    from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
    from app.schemas.email import AgentResult, EmailInput

    # Ensure dev-mode (no JOB_SECRET) regardless of local .env
    # (env vars take precedence over env_file in Settings)
    monkeypatch.setenv("JOB_SECRET", "")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()

    processed_label_id = "LBL_PROCESSED"

    class StubGmail:
        def ensure_label(self, *, name: str) -> str:  # type: ignore[no-untyped-def]
            assert name == "AI/Processed"
            return processed_label_id

        def list_message_metadatas(self, *, limit: int = 10, query: str | None = None):  # type: ignore[no-untyped-def]
            return [
                {"id": "m_processed", "labelIds": [processed_label_id]},
                {"id": "m_human", "labelIds": []},
                {"id": "m_noreply", "labelIds": []},
            ]

        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            return {"id": message_id, "threadId": "t1", "payload": {"headers": []}}

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            sender = "person@example.com"
            subject = "Hello"
            body = "Hi"
            if message_id == "m_noreply":
                sender = "no-reply@google.com"
                subject = "Security alert"
                body = "Security alert: new sign-in"
            return EmailInput(
                message_id=message_id,
                thread_id="t1",
                subject=subject,
                sender=sender,
                recipients=["me@example.com"],
                body_text=body,
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            assert draft_reply.strip()
            return "d1"

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            assert "AI/Processed" in label_names
            return label_names

    class StubAgent:
        def handle_email(self, email):  # type: ignore[no-untyped-def]
            if "no-reply" in (str(email.sender) if email.sender else ""):
                return AgentResult(
                    category=Category.other,
                    priority=Priority.medium,
                    summary="s",
                    needs_human_approval=True,
                    recommended_action=RecommendedAction.ignore,
                    draft_reply="",
                    reasoning_notes="n",
                    suggested_tool=SuggestedTool.none,
                    confidence=0.9,
                )
            return AgentResult(
                category=Category.other,
                priority=Priority.medium,
                summary="s",
                needs_human_approval=False,
                recommended_action=RecommendedAction.draft_for_review,
                draft_reply="Hello",
                reasoning_notes="n",
                suggested_tool=SuggestedTool.none,
                confidence=0.9,
            )

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_orchestrator] = lambda: StubAgent()

    client = TestClient(app)
    resp = client.post("/jobs/process-inbox", json={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["checked"] == 3
    assert data["skipped_already_processed"] == 1
    assert data["analyzed"] == 2
    assert data["drafts_created"] == 1
    assert data["skipped"] == 1
    assert set(data["processed_message_ids"]) == {"m_human", "m_noreply"}


def test_process_inbox_requires_secret_when_configured(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.jobs import get_orchestrator, get_gmail_service

    app = create_app()

    class StubGmail:
        def ensure_label(self, *, name: str) -> str:  # type: ignore[no-untyped-def]
            return "LBL_PROCESSED"

        def list_message_metadatas(self, *, limit: int = 10, query: str | None = None):  # type: ignore[no-untyped-def]
            return []

    class StubAgent:
        def handle_email(self, email):  # type: ignore[no-untyped-def]
            raise AssertionError("not used")

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_orchestrator] = lambda: StubAgent()

    # Configure secret via env + clear Settings cache
    monkeypatch.setenv("JOB_SECRET", "s3cr3t")
    from app.config import get_settings

    get_settings.cache_clear()

    client = TestClient(app)

    resp_missing = client.post("/jobs/process-inbox", json={"limit": 1})
    assert resp_missing.status_code == 403

    resp_wrong = client.post("/jobs/process-inbox", json={"limit": 1}, headers={"X-Job-Secret": "wrong"})
    assert resp_wrong.status_code == 403

    resp_ok = client.post("/jobs/process-inbox", json={"limit": 1}, headers={"X-Job-Secret": "s3cr3t"})
    assert resp_ok.status_code == 200

