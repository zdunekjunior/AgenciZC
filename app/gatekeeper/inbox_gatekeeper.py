from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import RecommendedAction
from app.schemas.email import AgentResult, EmailInput


class InboxDecision(str):
    """
    Gatekeeper decision for whether we should produce a reply draft.
    """


DECISION_REPLY_NEEDED: InboxDecision = "reply_needed"
DECISION_REVIEW_ONLY: InboxDecision = "review_only"
DECISION_IGNORE: InboxDecision = "ignore"


@dataclass(frozen=True)
class GatekeeperResult:
    decision: InboxDecision
    reason: str
    confidence: float


_NO_REPLY_PAT = re.compile(r"(no[-_. ]?reply|do[-_. ]?not[-_. ]?reply|donotreply)", re.IGNORECASE)
_AUTO_PAT = re.compile(r"(automated message|wiadomość automatyczna|powiadomien|notification|system)", re.IGNORECASE)

_SECURITY_PAT = re.compile(
    r"(security alert|alert bezpieczeństwa|new sign[- ]?in|logowan|password reset|verification|verify|kod.*weryfik)",
    re.IGNORECASE,
)

_BILLING_PAT = re.compile(
    r"(invoice|receipt|billing|renewal|subscription|faktura|rachunek|płatno|platno|opłacon|oplacon|proforma)",
    re.IGNORECASE,
)

_BOOKING_PAT = re.compile(
    r"(booking|reservation|confirmation|confirmed|rezerwac|potwierdzen|zamówienie|zamowienie|order|delivery|wysyłk|wysylk)",
    re.IGNORECASE,
)

_MARKETING_PAT = re.compile(
    r"(newsletter|unsubscribe|campaign|promo|promotion|reklam|marketing|sale\b|discount|zniżk|znizk|oferta specjalna)",
    re.IGNORECASE,
)

_HUMAN_REPLY_KEYWORDS = re.compile(r"(reklamac|zwrot|pomoc|problem|prosz[eę]\s+o\s+odpowiedź|please\s+reply|\?)", re.IGNORECASE)


def decide_inbox(*, email: EmailInput, analysis: AgentResult) -> GatekeeperResult:
    """
    Deterministic gatekeeper: prefer fewer drafts over bad drafts.
    """

    sender = (str(email.sender) if email.sender else "").strip()
    subj = (email.subject or "").strip()
    body = (email.body_text or "").strip()
    text = f"{sender}\n{subj}\n{body}"

    # Hard ignore: no-reply / security / system.
    if _NO_REPLY_PAT.search(sender) or _NO_REPLY_PAT.search(text):
        return GatekeeperResult(decision=DECISION_IGNORE, reason="pattern:no_reply", confidence=0.9)
    if _SECURITY_PAT.search(text):
        return GatekeeperResult(decision=DECISION_IGNORE, reason="pattern:security_alert", confidence=0.9)
    if _AUTO_PAT.search(text):
        return GatekeeperResult(decision=DECISION_IGNORE, reason="pattern:automated_system", confidence=0.85)

    # Review-only: transactional/marketing/billing (usually no reply needed).
    if _BILLING_PAT.search(text):
        return GatekeeperResult(decision=DECISION_REVIEW_ONLY, reason="pattern:billing_transactional", confidence=0.8)
    if _BOOKING_PAT.search(text):
        return GatekeeperResult(decision=DECISION_REVIEW_ONLY, reason="pattern:booking_confirmation", confidence=0.8)
    if _MARKETING_PAT.search(text):
        return GatekeeperResult(decision=DECISION_REVIEW_ONLY, reason="pattern:marketing_newsletter", confidence=0.8)

    # If the system already marked this as requiring human approval, we still treat it as reply-needed,
    # but it will remain draft-for-review (never auto-send).
    if bool(getattr(analysis, "needs_human_approval", False)):
        return GatekeeperResult(decision=DECISION_REPLY_NEEDED, reason="needs_human_approval", confidence=0.75)

    # Strong signal of a human needing a reply (support/complaint/business).
    try:
        if getattr(analysis, "category", None) is not None and getattr(analysis.category, "value", str(analysis.category)) in {
            "support",
            "complaint",
            "sales_inquiry",
            "partnership",
            "meeting_request",
        }:
            return GatekeeperResult(decision=DECISION_REPLY_NEEDED, reason="model_category:reply_needed", confidence=0.75)
    except Exception:
        pass
    if _HUMAN_REPLY_KEYWORDS.search(text):
        return GatekeeperResult(decision=DECISION_REPLY_NEEDED, reason="pattern:human_reply_keywords", confidence=0.7)

    # Low model confidence -> conservative.
    try:
        if float(analysis.confidence) < 0.55:
            return GatekeeperResult(decision=DECISION_REVIEW_ONLY, reason="low_model_confidence", confidence=0.7)
    except Exception:
        return GatekeeperResult(decision=DECISION_REVIEW_ONLY, reason="invalid_model_confidence", confidence=0.7)

    # If model already thinks ignore -> honor it.
    if analysis.recommended_action == RecommendedAction.ignore:
        return GatekeeperResult(decision=DECISION_IGNORE, reason="model_ignore", confidence=0.7)

    # Default: reply needed (human-like).
    return GatekeeperResult(decision=DECISION_REPLY_NEEDED, reason="default_human_message", confidence=0.65)

