from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_gmail_not_configured_returns_503(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from fastapi import HTTPException

    from app.api.routes.gmail import get_gmail_service

    app = create_app()
    app.dependency_overrides[get_gmail_service] = lambda: (_ for _ in ()).throw(
        HTTPException(status_code=503, detail="Gmail integration not configured: Missing GOOGLE_CLIENT_ID in environment")
    )

    client = TestClient(app)
    resp = client.post("/gmail/analyze-message", json={"message_id": "abc"})
    assert resp.status_code == 503
    assert "Gmail integration not configured" in resp.text


def test_analyze_message_nonexistent_id_returns_404(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.gmail import get_email_agent, get_gmail_service
    from app.integrations.gmail.service import GmailApiError

    app = create_app()

    class StubGmail:
        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            raise GmailApiError("Gmail message not found", status_code=404)

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            raise AssertionError("Should not be called when message missing")

    class StubAgent:
        def analyze_email(self, email):  # type: ignore[no-untyped-def]
            raise AssertionError("Should not be called when message missing")

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_email_agent] = lambda: StubAgent()

    client = TestClient(app)
    resp = client.post("/gmail/analyze-message", json={"message_id": "missing"})
    assert resp.status_code == 404


def test_list_messages_with_mocked_gmail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.gmail import get_gmail_service

    app = create_app()

    class StubGmail:
        def list_recent_messages(self, *, limit: int = 10):  # type: ignore[no-untyped-def]
            return [
                {
                    "id": "m1",
                    "threadId": "t1",
                    "snippet": "Hello",
                    "internalDate": "1710000000000",
                    "payload": {"headers": [{"name": "Subject", "value": "S"}, {"name": "From", "value": "a@b.com"}]},
                }
            ]

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()

    client = TestClient(app)
    resp = client.get("/gmail/messages?limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["messages"][0]["message_id"] == "m1"
    assert data["messages"][0]["thread_id"] == "t1"


def test_create_draft_skipped_when_draft_reply_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.gmail import get_email_agent, get_gmail_service

    app = create_app()

    class StubGmail:
        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            return {"id": message_id, "threadId": "t1", "payload": {"headers": []}}

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            from app.schemas.email import EmailInput

            return EmailInput(
                message_id=message_id,
                thread_id="t1",
                subject="x",
                sender="a@b.com",
                recipients=["c@d.com"],
                body_text="x",
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            raise AssertionError("Should not be called when draft_reply is empty")

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            assert "AI/Analyzed" in label_names
            assert "AI/Skipped" in label_names
            return label_names

    class StubAgent:
        def analyze_email(self, email):  # type: ignore[no-untyped-def]
            from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
            from app.schemas.email import AgentResult

            return AgentResult(
                category=Category.other,
                priority=Priority.medium,
                summary="s",
                needs_human_approval=False,
                recommended_action=RecommendedAction.draft_for_review,
                draft_reply="",
                reasoning_notes="n",
                suggested_tool=SuggestedTool.none,
                confidence=0.9,
            )

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_email_agent] = lambda: StubAgent()

    client = TestClient(app)
    resp = client.post("/gmail/analyze-and-create-draft", json={"message_id": "m1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft"]["status"] == "skipped"
    assert data["draft"]["reason"] == "auto_system_message"
    assert data["action_taken"] == "skipped"
    assert "AI/Skipped" in data["label_applied"]


def test_create_draft_success_with_mocked_gmail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.gmail import get_email_agent, get_gmail_service

    app = create_app()

    class StubGmail:
        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            return {"id": message_id, "threadId": "t1", "payload": {"headers": []}}

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            from app.schemas.email import EmailInput

            return EmailInput(
                message_id=message_id,
                thread_id="t1",
                subject="x",
                sender="a@b.com",
                recipients=["c@d.com"],
                body_text="x",
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            assert draft_reply.strip()
            return "d_123"

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            assert "AI/Analyzed" in label_names
            assert "AI/DraftCreated" in label_names
            return label_names

    class StubAgent:
        def analyze_email(self, email):  # type: ignore[no-untyped-def]
            from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
            from app.schemas.email import AgentResult

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
    app.dependency_overrides[get_email_agent] = lambda: StubAgent()

    client = TestClient(app)
    resp = client.post("/gmail/analyze-and-create-draft", json={"message_id": "m1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft"]["status"] == "created"
    assert data["draft"]["draft_id"] == "d_123"
    assert data["action_taken"] == "draft_created"
    assert "AI/DraftCreated" in data["label_applied"]


def test_create_draft_skipped_when_agent_recommended_ignore(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.api.routes.gmail import get_email_agent, get_gmail_service

    app = create_app()

    class StubGmail:
        def fetch_message(self, *, message_id: str):  # type: ignore[no-untyped-def]
            return {"id": message_id, "threadId": "t1", "payload": {"headers": []}}

        def fetch_email_input(self, *, message_id: str):  # type: ignore[no-untyped-def]
            from app.schemas.email import EmailInput

            return EmailInput(
                message_id=message_id,
                thread_id="t1",
                subject="Google security alert",
                sender="no-reply@google.com",
                recipients=["me@example.com"],
                body_text="Security alert: new sign-in detected",
                thread_context=[],
            )

        def create_reply_draft(self, *, original_message, draft_reply: str):  # type: ignore[no-untyped-def]
            raise AssertionError("Should not create draft when ignore")

        def apply_labels(self, *, message_id: str, label_names: list[str]):  # type: ignore[no-untyped-def]
            assert "AI/Analyzed" in label_names
            assert "AI/Skipped" in label_names
            return label_names

    class StubAgent:
        def analyze_email(self, email):  # type: ignore[no-untyped-def]
            from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
            from app.schemas.email import AgentResult

            return AgentResult(
                category=Category.other,
                priority=Priority.medium,
                summary="s",
                needs_human_approval=True,
                recommended_action=RecommendedAction.ignore,
                draft_reply="Should be ignored",
                reasoning_notes="n",
                suggested_tool=SuggestedTool.none,
                confidence=0.9,
            )

    app.dependency_overrides[get_gmail_service] = lambda: StubGmail()
    app.dependency_overrides[get_email_agent] = lambda: StubAgent()

    client = TestClient(app)
    resp = client.post("/gmail/analyze-and-create-draft", json={"message_id": "m1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["draft"]["status"] == "skipped"
    assert data["draft"]["reason"] == "auto_system_message"
    assert data["action_taken"] == "skipped"
    assert "AI/Skipped" in data["label_applied"]

