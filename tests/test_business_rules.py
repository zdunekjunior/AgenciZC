from app.domain.enums import RecommendedAction
from app.schemas.email import EmailInput


def test_sales_email_price_forces_human_approval() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    payload = {
        "subject": "Prośba o ofertę",
        "from_email": "client@example.com",
        "to_email": "me@example.com",
        "body": "Poproszę ofertę indywidualną i cenę za wdrożenie.",
        "thread_context": [],
    }
    resp = client.post("/agent/analyze-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_human_approval"] is True
    assert data["recommended_action"] == RecommendedAction.draft_for_review.value


def test_complaint_forces_human_approval() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    payload = {
        "subject": "Reklamacja",
        "from_email": "client@example.com",
        "to_email": "me@example.com",
        "body": "Składam reklamację: usługa nie działa od wczoraj. Proszę o pilny zwrot.",
        "thread_context": [],
    }
    resp = client.post("/agent/analyze-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_human_approval"] is True
    assert data["recommended_action"] == RecommendedAction.draft_for_review.value


def test_simple_contact_request_can_be_no_approval_in_mock() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    payload = {
        "subject": "Kontakt",
        "from_email": "client@example.com",
        "to_email": "me@example.com",
        "body": "Cześć, czy możemy się zdzwonić jutro po południu?",
        "thread_context": [],
    }
    resp = client.post("/agent/analyze-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # In mock mode the model returns low-risk output; hard rules shouldn't force approval here.
    assert isinstance(data["needs_human_approval"], bool)
    assert data["recommended_action"] in {
        "draft_for_review",
        "ask_human",
        "ignore",
    }


def test_fallback_when_model_returns_partial_data() -> None:
    """
    Unit test of normalization path: if model output is partial/invalid, we still return safe AgentResult.
    """

    from app.agents.email_agent import EmailAgent
    from app.services.openai_client import OpenAIResponse

    class StubClient:
        def create_response_json(self, **kwargs):  # type: ignore[no-untyped-def]
            return OpenAIResponse(output_text=json_str)

    json_str = '{"category":"nonsense","confidence": 2, "draft_reply": ""}'
    agent = EmailAgent(client=StubClient())  # type: ignore[arg-type]
    email = EmailInput(
        message_id="m_partial",
        subject="Pytanie",
        sender="client@example.com",
        recipients=["me@example.com"],
        body_text="Hej, macie chwilę na rozmowę?",
    )
    result = agent.analyze_email(email)
    assert 0.0 <= result.confidence <= 1.0
    assert result.draft_reply
    assert result.category.value in {
        "sales_inquiry",
        "support",
        "complaint",
        "invoice",
        "meeting_request",
        "partnership",
        "other",
    }


def test_google_security_alert_forces_ignore_and_empty_draft() -> None:
    from app.agents.rules.email_rules import enforce_business_rules
    from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
    from app.schemas.email import AgentResult

    email = EmailInput(
        message_id="m_sys",
        subject="Google Security Alert",
        sender="no-reply@google.com",
        recipients=["me@example.com"],
        body_text="Security alert: new sign-in detected",
        thread_context=[],
    )
    model_result = AgentResult(
        category=Category.other,
        priority=Priority.medium,
        summary="s",
        needs_human_approval=False,
        recommended_action=RecommendedAction.draft_for_review,
        draft_reply="Draft that should be removed",
        reasoning_notes="n",
        suggested_tool=SuggestedTool.none,
        confidence=0.9,
    )
    final = enforce_business_rules(email, model_result)
    assert final.recommended_action == RecommendedAction.ignore
    assert final.draft_reply == ""


def test_no_reply_sender_forces_ignore() -> None:
    from app.agents.rules.email_rules import enforce_business_rules
    from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
    from app.schemas.email import AgentResult

    email = EmailInput(
        message_id="m_nr",
        subject="Powiadomienie",
        sender="donotreply@platform.example",
        recipients=["me@example.com"],
        body_text="Twoje konto zostało zaktualizowane.",
        thread_context=[],
    )
    model_result = AgentResult(
        category=Category.other,
        priority=Priority.medium,
        summary="s",
        needs_human_approval=False,
        recommended_action=RecommendedAction.draft_for_review,
        draft_reply="Draft that should be removed",
        reasoning_notes="n",
        suggested_tool=SuggestedTool.none,
        confidence=0.9,
    )
    final = enforce_business_rules(email, model_result)
    assert final.recommended_action == RecommendedAction.ignore
    assert final.draft_reply == ""

