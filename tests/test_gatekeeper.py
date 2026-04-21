from __future__ import annotations

from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
from app.gatekeeper.inbox_gatekeeper import DECISION_IGNORE, DECISION_REPLY_NEEDED, DECISION_REVIEW_ONLY, decide_inbox
from app.schemas.email import AgentResult, EmailInput


def _analysis(conf: float = 0.9, action: RecommendedAction = RecommendedAction.draft_for_review) -> AgentResult:
    return AgentResult(
        category=Category.other,
        priority=Priority.medium,
        summary="s",
        needs_human_approval=False,
        recommended_action=action,
        draft_reply="hi",
        reasoning_notes="n",
        suggested_tool=SuggestedTool.none,
        confidence=conf,
    )


def test_newsletter_marketing_is_review_only() -> None:
    email = EmailInput(
        message_id="m1",
        subject="Newsletter: promo - unsubscribe",
        sender="news@promo.example.com",
        recipients=["me@example.com"],
        body_text="Great discount. Unsubscribe here.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis())
    assert g.decision == DECISION_REVIEW_ONLY


def test_billing_renewal_is_review_only() -> None:
    email = EmailInput(
        message_id="m2",
        subject="Invoice / renewal notice",
        sender="billing@example.com",
        recipients=["me@example.com"],
        body_text="Receipt and billing renewal.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis())
    assert g.decision == DECISION_REVIEW_ONLY


def test_booking_confirmation_is_review_only() -> None:
    email = EmailInput(
        message_id="m3",
        subject="Reservation confirmation",
        sender="booking@example.com",
        recipients=["me@example.com"],
        body_text="Your booking is confirmed.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis())
    assert g.decision == DECISION_REVIEW_ONLY


def test_security_alert_is_ignore() -> None:
    email = EmailInput(
        message_id="m4",
        subject="Security alert: new sign-in",
        sender="no-reply@google.com",
        recipients=["me@example.com"],
        body_text="New sign-in detected. Do not reply.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis())
    assert g.decision == DECISION_IGNORE


def test_human_business_question_is_reply_needed() -> None:
    email = EmailInput(
        message_id="m5",
        subject="Oferta współpracy",
        sender="person@example.com",
        recipients=["me@example.com"],
        body_text="Czy możemy porozmawiać o współpracy i wdrożeniu? Proszę o odpowiedź.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis(conf=0.9))
    assert g.decision == DECISION_REPLY_NEEDED


def test_low_confidence_defaults_to_review_only() -> None:
    email = EmailInput(
        message_id="m6",
        subject="Pytanie",
        sender="person@example.com",
        recipients=["me@example.com"],
        body_text="Hej, szybkie pytanie.",
        thread_context=[],
    )
    g = decide_inbox(email=email, analysis=_analysis(conf=0.2))
    assert g.decision == DECISION_REVIEW_ONLY

