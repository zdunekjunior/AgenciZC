from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import Priority, RecommendedAction
from app.schemas.email import AgentResult, EmailInput


_APPROVAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcen(a|y|ę)\b", re.IGNORECASE),
    re.compile(r"\bwycen(a|y|ę)\b", re.IGNORECASE),
    re.compile(r"\bumowa\b", re.IGNORECASE),
    re.compile(r"\breklamacj[aei]\b", re.IGNORECASE),
    re.compile(r"\bzwrot\b", re.IGNORECASE),
    re.compile(r"\bfaktura\b", re.IGNORECASE),
    re.compile(r"\bpłatno(?:ść|sci)\b", re.IGNORECASE),
    re.compile(r"\btermin(?:\s+realizacji)?\b", re.IGNORECASE),
    re.compile(r"\bnegocjacj[aei]\b", re.IGNORECASE),
    re.compile(r"\bofert\w*\s+indywidualn\w*\b", re.IGNORECASE),
]

_NO_REPLY_SENDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"no[-_.]?reply", re.IGNORECASE),
    re.compile(r"do[-_.]?not[-_.]?reply", re.IGNORECASE),
    re.compile(r"donotreply", re.IGNORECASE),
]

_SYSTEM_SUBJECT_BODY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsecurity\s*alert\b", re.IGNORECASE),
    re.compile(r"\balert\s+bezpieczeństwa\b", re.IGNORECASE),
    re.compile(r"\blogowan", re.IGNORECASE),
    re.compile(r"\bnew\s+sign[- ]?in\b", re.IGNORECASE),
    re.compile(r"\breset\b.*\bhas", re.IGNORECASE),
    re.compile(r"\bpassword\b.*\breset\b", re.IGNORECASE),
    re.compile(r"\bverification\b", re.IGNORECASE),
    re.compile(r"\bverify\b", re.IGNORECASE),
    re.compile(r"\bkod\b.*\bweryfik", re.IGNORECASE),
    re.compile(r"\bpotwierd", re.IGNORECASE),
    re.compile(r"\bautomatyczn", re.IGNORECASE),
    re.compile(r"\bpowiadomien", re.IGNORECASE),
    re.compile(r"\bnotification\b", re.IGNORECASE),
    re.compile(r"\bsystem\b", re.IGNORECASE),
]

_SYSTEM_SENDER_DOMAINS: set[str] = {
    "accounts.google.com",
    "google.com",
    "mail.google.com",
    "microsoft.com",
    "account.microsoft.com",
    "paypal.com",
}


@dataclass(frozen=True)
class RulesDecision:
    needs_human_approval: bool
    reason: str | None = None


def should_force_human_approval(email: EmailInput) -> RulesDecision:
    text = " ".join([email.subject or "", email.body_text]).strip()
    for pat in _APPROVAL_PATTERNS:
        if pat.search(text):
            return RulesDecision(needs_human_approval=True, reason=f"keyword_match:{pat.pattern}")
    return RulesDecision(needs_human_approval=False)


@dataclass(frozen=True)
class NonReplyableDecision:
    is_non_replyable: bool
    reason: str | None = None


def detect_non_replyable(email: EmailInput) -> NonReplyableDecision:
    sender = (str(email.sender) if email.sender else "").strip()
    subj = (email.subject or "").strip()
    body = (email.body_text or "").strip()
    text = f"{subj}\n{body}"

    for pat in _NO_REPLY_SENDER_PATTERNS:
        if pat.search(sender):
            return NonReplyableDecision(True, reason="no_reply_sender")

    sender_domain = sender.split("@")[-1].lower() if "@" in sender else ""
    if sender_domain in _SYSTEM_SENDER_DOMAINS:
        for pat in _SYSTEM_SUBJECT_BODY_PATTERNS:
            if pat.search(text):
                return NonReplyableDecision(True, reason="system_security_alert")

    for pat in _SYSTEM_SUBJECT_BODY_PATTERNS:
        if pat.search(text):
            return NonReplyableDecision(True, reason="system_message")

    return NonReplyableDecision(False, reason=None)


def enforce_business_rules(email: EmailInput, result: AgentResult) -> AgentResult:
    """
    Backend hard rules (must win over model output).
    """

    non_replyable = detect_non_replyable(email)
    if non_replyable.is_non_replyable:
        return result.model_copy(
            update={
                "recommended_action": RecommendedAction.ignore,
                "needs_human_approval": True,
                "draft_reply": "",
                "reasoning_notes": "Wiadomość wygląda na automatyczną/systemową lub no-reply. Nie tworzę draftu odpowiedzi.",
                "confidence": min(result.confidence, 0.6),
            }
        )

    approval = should_force_human_approval(email)

    needs_approval = bool(result.needs_human_approval)
    if approval.needs_human_approval:
        needs_approval = True

    if result.priority == Priority.high:
        needs_approval = True

    if result.confidence < 0.45:
        needs_approval = True

    recommended_action = result.recommended_action
    if needs_approval:
        recommended_action = RecommendedAction.draft_for_review

    # Guardrail: never allow "send_now" or any send-like behavior.
    # RecommendedAction is enum-restricted anyway; this is an extra defensive layer.
    if str(recommended_action).lower() == "send_now":
        recommended_action = RecommendedAction.draft_for_review
        needs_approval = True

    return result.model_copy(
        update={
            "needs_human_approval": needs_approval,
            "recommended_action": recommended_action,
        }
    )

