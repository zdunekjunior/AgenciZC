from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agents.rules.email_rules import enforce_business_rules
from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
from app.schemas.email import AgentResult, AgentResultPartial, EmailInput
from app.services.openai_client import OpenAIResponsesClient
from app.tools.router import decide_tool

log = logging.getLogger(__name__)


EMAIL_AGENT_SYSTEM_PROMPT = """\
Jesteś backendowym agentem AI o roli: Inbox Assistant.

Cel:
- Analizujesz treść maila i zwracasz ustrukturyzowany wynik do stworzenia draftu odpowiedzi.
- Jesteś "draft-first": nigdy nie wysyłasz maili i nie sugerujesz automatycznego wysyłania.

Styl:
- Odpowiedzi krótkie, profesjonalne, bezpieczne.
- Jeśli brakuje danych lub temat jest ryzykowny, ustaw needs_human_approval=true.

Bezpieczeństwo:
- Nie składaj obietnic finansowych ani prawnych.
- Nie podawaj twardych wycen.
- Nie deklaruj terminów bez pewności.
- Unikaj kategorycznych stwierdzeń, jeśli brakuje danych.

Klasyfikacja:
- category: sales_inquiry | support | complaint | invoice | meeting_request | partnership | other
- priority: low | medium | high

Akcja:
- recommended_action: draft_for_review | ask_human | ignore
- Nigdy nie ustawiaj recommended_action na nic w rodzaju "send_now".

Wynik ma zawierać:
- summary: 1–3 zdania (bez dopowiadania faktów)
- draft_reply: propozycja odpowiedzi (najlepiej w języku maila; w razie wątpliwości po polsku)
- reasoning_notes: krótkie, biznesowe uzasadnienie (bez ujawniania szczegółowego rozumowania)
- suggested_tool: none | web_research (to tylko sugestia; narzędzia nie są wykonywane)
- confidence: liczba 0..1 (niższa gdy temat ryzykowny lub dane niepełne)

Zwróć wyłącznie JSON zgodny ze schemą (strict).\
"""


def _agent_result_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": {"type": "string", "enum": [c.value for c in Category]},
            "priority": {"type": "string", "enum": [p.value for p in Priority]},
            "summary": {"type": "string", "minLength": 1},
            "needs_human_approval": {"type": "boolean"},
            "recommended_action": {"type": "string", "enum": [a.value for a in RecommendedAction]},
            "draft_reply": {"type": "string"},
            "reasoning_notes": {"type": "string"},
            "suggested_tool": {"type": "string", "enum": [t.value for t in SuggestedTool]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "category",
            "priority",
            "summary",
            "needs_human_approval",
            "recommended_action",
            "draft_reply",
            "reasoning_notes",
            "suggested_tool",
            "confidence",
        ],
    }


def _safe_fallback_reply(email: EmailInput) -> str:
    subj = (email.subject or "").strip()
    if subj:
        return (
            f"Dzień dobry, dziękuję za wiadomość w sprawie „{subj}”. "
            "Potwierdzam otrzymanie — wrócę z odpowiedzią po weryfikacji szczegółów. Pozdrawiam."
        )
    return (
        "Dzień dobry, dziękuję za wiadomość. "
        "Potwierdzam otrzymanie — wrócę z odpowiedzią po weryfikacji szczegółów. Pozdrawiam."
    )


def _fallback_raw(email: EmailInput) -> dict[str, Any]:
    return {
        "category": "other",
        "priority": "medium",
        "summary": "Wiadomość wymaga przygotowania odpowiedzi.",
        "needs_human_approval": True,
        "recommended_action": "draft_for_review",
        "draft_reply": _safe_fallback_reply(email),
        "reasoning_notes": "Fallback: bezpieczny wynik wygenerowany po błędzie wywołania lub parsowania.",
        "suggested_tool": "none",
        "confidence": 0.35,
    }


_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json_object(text: str) -> str | None:
    """
    Best-effort recovery: extract a JSON object from a larger text blob.
    """

    m = _JSON_OBJECT_RE.search(text)
    if not m:
        return None
    candidate = m.group(0).strip()
    return candidate or None


def _parse_model_json(text: str) -> dict[str, Any] | None:
    """
    Parse JSON; if it fails, try to recover a JSON object from text.
    """

    try:
        val = json.loads(text)
        return val if isinstance(val, dict) else None
    except Exception:
        recovered = _extract_json_object(text)
        if not recovered:
            return None
        try:
            val = json.loads(recovered)
            return val if isinstance(val, dict) else None
        except Exception:
            return None


def _coerce_enum(value: Any, enum_cls, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        key = value.strip().lower()
        for item in enum_cls:
            if item.value == key:
                return item
    return default


def _normalize_agent_output(email: EmailInput, partial: AgentResultPartial) -> AgentResult:
    category = _coerce_enum(partial.category, Category, Category.other)
    priority = _coerce_enum(partial.priority, Priority, Priority.medium)
    action = _coerce_enum(partial.recommended_action, RecommendedAction, RecommendedAction.draft_for_review)
    tool = _coerce_enum(partial.suggested_tool, SuggestedTool, SuggestedTool.none)

    summary = str(partial.summary).strip() if partial.summary is not None else ""
    if not summary:
        summary = "Wiadomość wymaga analizy i przygotowania odpowiedzi."

    draft_reply = str(partial.draft_reply).strip() if partial.draft_reply is not None else ""
    if not draft_reply:
        draft_reply = _safe_fallback_reply(email)

    reasoning_notes = str(partial.reasoning_notes).strip() if partial.reasoning_notes is not None else ""
    if not reasoning_notes:
        reasoning_notes = "Utworzono bezpieczny draft odpowiedzi na podstawie treści maila."

    try:
        confidence = float(partial.confidence) if partial.confidence is not None else 0.5
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    needs_human_approval = bool(partial.needs_human_approval) if partial.needs_human_approval is not None else True

    result = AgentResult(
        category=category,
        priority=priority,
        summary=summary,
        needs_human_approval=needs_human_approval,
        recommended_action=action,
        draft_reply=draft_reply,
        reasoning_notes=reasoning_notes,
        suggested_tool=tool,
        confidence=confidence,
    )
    return enforce_business_rules(email, result)


class EmailAgent:
    def __init__(self, *, client: OpenAIResponsesClient) -> None:
        self._client = client

    def analyze_email(self, email: EmailInput) -> AgentResult:
        routing = decide_tool(email)

        user_payload = {
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "subject": email.subject,
            "sender": str(email.sender) if email.sender else None,
            "recipients": [str(x) for x in email.recipients],
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "body_text": email.body_text,
            "tool_context": {
                "suggested_tool": routing.suggested_tool.value,
                "note": routing.note,
            },
        }

        try:
            resp = self._client.create_response_json(
                system_prompt=EMAIL_AGENT_SYSTEM_PROMPT,
                user_payload=user_payload,
                json_schema=_agent_result_json_schema(),
            )
            parsed = _parse_model_json(resp.output_text)
            if parsed is None:
                log.error("Model returned invalid JSON; using fallback", extra={"output_text": resp.output_text[:500]})
                raw = _fallback_raw(email)
            else:
                raw = parsed
        except Exception:  # noqa: BLE001
            log.exception("Agent model call failed; using fallback")
            raw = _fallback_raw(email)

        try:
            partial = AgentResultPartial.model_validate(raw)
        except ValidationError:
            partial = AgentResultPartial()

        if partial.suggested_tool is None:
            partial = partial.model_copy(update={"suggested_tool": routing.suggested_tool.value})

        return _normalize_agent_output(email, partial)

