from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import SuggestedTool
from app.schemas.email import EmailInput


@dataclass(frozen=True)
class ToolRoutingDecision:
    suggested_tool: SuggestedTool
    note: str = ""


def decide_tool(email: EmailInput) -> ToolRoutingDecision:
    """
    Placeholder router for future tools/function calling.

    For now we only *suggest* tools; we do not execute anything.
    """

    text = (email.subject or "") + "\n" + email.body_text
    if any(k in text.lower() for k in ["link", "źródło", "źrodlo", "sprawdź", "sprawdz", "research"]):
        return ToolRoutingDecision(
            suggested_tool=SuggestedTool.web_research,
            note="Potential need to verify external facts/links (placeholder).",
        )
    return ToolRoutingDecision(suggested_tool=SuggestedTool.none, note="No tool suggested.")

