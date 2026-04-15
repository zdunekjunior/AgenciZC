from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.team.draft_agent import DraftAgent, DraftAgentInput
from app.agents.team.inbox_agent import InboxAgent, InboxAgentInput
from app.agents.team.research_agent import ResearchAgent, ResearchAgentInput, ResearchAgentOutput
from app.audit.service import AuditLogService
from app.domain.audit import ActorType, EntityType
from app.domain.enums import Category, RecommendedAction
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
        audit: AuditLogService | None = None,
    ) -> None:
        self._inbox = inbox_agent
        self._draft = draft_agent
        self._research = research_agent
        self._audit = audit

    def handle_email(self, email: EmailInput) -> AgentResult:
        """
        Main orchestration entrypoint used by API endpoints and jobs.
        """

        if self._audit is not None:
            self._audit.log(
                entity_type=EntityType.email,
                entity_id=email.message_id,
                action="email_analyzed",
                actor_type=ActorType.orchestrator,
                actor_name="EmailOrchestrator",
                status="info",
                metadata={"thread_id": email.thread_id, "subject": email.subject},
            )

        inbox_run = self._inbox.run(InboxAgentInput(email=email))
        if inbox_run.output is None:
            # InboxAgent is required; if it fails, return a safe fallback shape.
            # Practically, current InboxAgent delegates to EmailAgent which already has fallbacks.
            raise RuntimeError("InboxAgent returned no output")

        result = inbox_run.output

        research_out: ResearchAgentOutput | None = None

        # Routing decision: business/complex emails -> ResearchAgent.
        needs_research = self._should_route_to_research(email=email, result=result)
        if needs_research:
            research_run = self._research.run(
                ResearchAgentInput(
                    email=email,
                    category=result.category if isinstance(result.category, Category) else None,
                )
            )
            research_out = research_run.output
            if self._audit is not None:
                self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="research_executed",
                    actor_type=ActorType.agent,
                    actor_name="ResearchAgent",
                    status="ok" if research_out is not None else "error",
                    metadata={
                        "category": getattr(result.category, "value", str(result.category)),
                        "has_output": bool(research_out),
                    },
                )
            # Keep the external shape compatible, but annotate reasoning.
            result = result.model_copy(
                update={
                    "needs_human_approval": True,
                    "reasoning_notes": (result.reasoning_notes + " | Routed to ResearchAgent.").strip(" |"),
                    "confidence": min(float(result.confidence), 0.7),
                }
            )

        # Draft agent: finalize draft text for review flows.
        if result.recommended_action != RecommendedAction.ignore:
            draft_run = self._draft.run(DraftAgentInput(email=email, draft_reply=result.draft_reply, research=research_out))
            if draft_run.output is not None:
                result = result.model_copy(update={"draft_reply": draft_run.output.draft_reply})

        return result

    @staticmethod
    def _should_route_to_research(*, email: EmailInput, result: AgentResult) -> bool:
        """
        Business rule: route to ResearchAgent for offer/partnership/collaboration/complex business inquiries.
        """

        if result.category in (Category.partnership, Category.sales_inquiry):
            return True

        text = ((email.subject or "") + "\n" + (email.body_text or "")).lower()
        keywords = [
            "oferta",
            "propozycja",
            "partnerstwo",
            "współpraca",
            "wspolpraca",
            "wspólnie",
            "wspolnie",
            "proposal",
            "partnership",
            "collaboration",
            "biznes",
            "współdział",
            "wspoldzial",
        ]
        if any(k in text for k in keywords):
            return True

        # Low confidence -> treat as complex.
        try:
            if float(result.confidence) < 0.45:
                return True
        except Exception:
            return True

        return False

