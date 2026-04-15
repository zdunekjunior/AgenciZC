from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.team.draft_agent import DraftAgent, DraftAgentInput
from app.agents.team.inbox_agent import InboxAgent, InboxAgentInput
from app.agents.team.research_agent import ResearchAgent, ResearchAgentInput
from app.domain.enums import RecommendedAction, SuggestedTool
from app.schemas.email import AgentResult, EmailInput


@dataclass(frozen=True)
class OrchestrationTrace:
    """
    Internal trace of orchestration steps (not returned by public APIs yet).
    """

    steps: list[str] = field(default_factory=list)


class EmailOrchestrator:
    """
    Orchestrates multiple agents for an email case.

    Compatibility rule: the system still returns AgentResult (same as today),
    but internally it can route to multiple agents.
    """

    def __init__(
        self,
        *,
        inbox_agent: InboxAgent,
        draft_agent: DraftAgent,
        research_agent: ResearchAgent,
    ) -> None:
        self._inbox = inbox_agent
        self._draft = draft_agent
        self._research = research_agent

    def handle_email(self, email: EmailInput) -> AgentResult:
        """
        Main orchestration entrypoint used by API endpoints and jobs.
        """

        inbox_run = self._inbox.run(InboxAgentInput(email=email))
        if inbox_run.output is None:
            # InboxAgent is required; if it fails, return a safe fallback shape.
            # Practically, current InboxAgent delegates to EmailAgent which already has fallbacks.
            raise RuntimeError("InboxAgent returned no output")

        result = inbox_run.output

        # Routing decision: if model suggests research, call ResearchAgent (stub for now).
        needs_research = result.suggested_tool == SuggestedTool.web_research
        if needs_research:
            self._research.run(
                ResearchAgentInput(
                    email=email,
                    query=f"{email.subject or ''}\n{email.body_text}".strip()[:300],
                )
            )
            # While research is stubbed, we keep behavior compatible: we do not change content,
            # but we make the “needs human” posture slightly more conservative.
            result = result.model_copy(
                update={
                    "needs_human_approval": True,
                    "reasoning_notes": (result.reasoning_notes + " | Routed to ResearchAgent (stub).").strip(" |"),
                    "confidence": min(float(result.confidence), 0.6),
                }
            )

        # Draft agent: finalize draft text for review flows.
        if result.recommended_action != RecommendedAction.ignore:
            draft_run = self._draft.run(DraftAgentInput(email=email, draft_reply=result.draft_reply))
            if draft_run.output is not None:
                result = result.model_copy(update={"draft_reply": draft_run.output.draft_reply})

        return result

