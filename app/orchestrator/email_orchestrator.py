from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.team.draft_agent import DraftAgent, DraftAgentInput
from app.agents.team.inbox_agent import InboxAgent, InboxAgentInput
from app.agents.team.lead_scoring_agent import LeadScoringAgent, LeadScoringAgentInput
from app.agents.team.research_agent import ResearchAgent, ResearchAgentInput, ResearchAgentOutput
from app.audit.service import AuditLogService
from app.agents.company.sales_agent import SalesAgent, SalesAgentInput
from app.agents.company.professor_agent import ProfessorAgent, ProfessorAgentInput
from app.cases.service import CaseService
from app.domain.audit import ActorType, EntityType
from app.domain.enums import Category, RecommendedAction
from app.gatekeeper.inbox_gatekeeper import DECISION_IGNORE, DECISION_REPLY_NEEDED, decide_inbox
from app.leads.service import LeadService
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
        lead_scoring_agent: LeadScoringAgent | None = None,
        sales_agent: SalesAgent | None = None,
        professor_agent: ProfessorAgent | None = None,
        leads: LeadService | None = None,
        cases: CaseService | None = None,
        audit: AuditLogService | None = None,
    ) -> None:
        self._inbox = inbox_agent
        self._draft = draft_agent
        self._research = research_agent
        self._lead = lead_scoring_agent
        self._sales = sales_agent
        self._prof = professor_agent
        self._leads = leads
        self._cases = cases
        self._audit = audit

    def handle_email(self, email: EmailInput) -> AgentResult:
        """
        Main orchestration entrypoint used by API endpoints and jobs.
        """

        case = None
        if self._cases is not None:
            # Prefer that callers create the case with a more specific source_type (api/gmail/job).
            case = self._cases.get_or_create_from_email(email=email, source_type="other")
            case = self._cases.add_assigned_agent(case=case, agent_name="EmailOrchestrator")

        if self._audit is not None:
            ev = self._audit.log(
                entity_type=EntityType.email,
                entity_id=email.message_id,
                action="email_analyzed",
                actor_type=ActorType.orchestrator,
                actor_name="EmailOrchestrator",
                status="info",
                metadata={"thread_id": email.thread_id, "subject": email.subject},
            )
            if case is not None and self._cases is not None:
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)
                case = self._cases.touch_status(case=case, status="analyzed")

        inbox_run = self._inbox.run(InboxAgentInput(email=email))
        if inbox_run.output is None:
            # InboxAgent is required; if it fails, return a safe fallback shape.
            # Practically, current InboxAgent delegates to EmailAgent which already has fallbacks.
            raise RuntimeError("InboxAgent returned no output")

        result = inbox_run.output
        if case is not None and self._cases is not None:
            case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._inbox, "name", "InboxAgent"))

        # Gatekeeper: decide whether a draft should be created at all.
        gate = decide_inbox(email=email, analysis=result)
        # If backend rules already require human approval, we still allow a draft-for-review
        # (human-in-the-loop), unless it's a hard ignore.
        if bool(result.needs_human_approval) and gate.decision != DECISION_IGNORE:
            from app.gatekeeper.inbox_gatekeeper import GatekeeperResult  # local import to avoid cycles

            gate = GatekeeperResult(decision=DECISION_REPLY_NEEDED, reason=f"{gate.reason}|needs_human_approval_override", confidence=gate.confidence)
        if case is not None and self._cases is not None:
            skipped_reason = gate.reason if gate.decision != DECISION_REPLY_NEEDED else None
            case = self._cases.set_inbox_decision(case=case, decision=gate.decision, reason=gate.reason, skipped_reason=skipped_reason)
            if self._audit is not None:
                ev = self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="inbox_decision_recorded",
                    actor_type=ActorType.orchestrator,
                    actor_name="EmailOrchestrator",
                    status="info",
                    metadata={"decision": gate.decision, "reason": gate.reason, "gk_confidence": gate.confidence},
                )
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

        # Enforce policy on external result shape:
        # - ignore/review_only -> no draft content (prevents downstream draft creation)
        # - ignore -> recommended_action=ignore
        if gate.decision != DECISION_REPLY_NEEDED:
            result = result.model_copy(
                update={
                    "draft_reply": "",
                    "recommended_action": RecommendedAction.ignore if gate.decision == DECISION_IGNORE else RecommendedAction.ask_human,
                    "reasoning_notes": (result.reasoning_notes + f" | Gatekeeper:{gate.decision}:{gate.reason}").strip(" |"),
                    "confidence": min(float(result.confidence), 0.7),
                }
            )
        research_out: ResearchAgentOutput | None = None

        # Routing decision: business/complex emails -> ResearchAgent.
        needs_research = self._should_route_to_research(email=email, result=result)
        if needs_research:
            if case is not None and self._cases is not None:
                case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._research, "name", "ResearchAgent"))
            research_run = self._research.run(
                ResearchAgentInput(
                    email=email,
                    category=result.category if isinstance(result.category, Category) else None,
                )
            )
            research_out = research_run.output
            if self._audit is not None:
                ev = self._audit.log(
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
                if case is not None and self._cases is not None:
                    case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

            if case is not None and self._cases is not None and research_out is not None:
                case = self._cases.set_research_summary(case=case, research_summary=research_out.research_summary)
                case = self._cases.touch_status(case=case, status="research_added")
            # Keep the external shape compatible, but annotate reasoning.
            result = result.model_copy(
                update={
                    "needs_human_approval": True,
                    "reasoning_notes": (result.reasoning_notes + " | Routed to ResearchAgent.").strip(" |"),
                    "confidence": min(float(result.confidence), 0.7),
                }
            )

        # Draft agent: finalize draft text only when gatekeeper says reply_needed.
        if gate.decision == DECISION_REPLY_NEEDED and result.recommended_action != RecommendedAction.ignore:
            if case is not None and self._cases is not None:
                case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._draft, "name", "DraftAgent"))
            draft_run = self._draft.run(DraftAgentInput(email=email, draft_reply=result.draft_reply, research=research_out))
            if draft_run.output is not None:
                result = result.model_copy(update={"draft_reply": draft_run.output.draft_reply})

        # Lead scoring (business-only) -> store + audit
        if self._lead is not None and self._leads is not None and self._should_score_lead(email=email, result=result):
            if case is not None and self._cases is not None:
                case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._lead, "name", "LeadScoringAgent"))
            lead_run = self._lead.run(LeadScoringAgentInput(email=email, analysis=result, research=research_out))
            if lead_run.output is not None:
                self._leads.upsert(entity_id=email.message_id, scoring=lead_run.output)
                if self._audit is not None:
                    ev = self._audit.log(
                        entity_type=EntityType.email,
                        entity_id=email.message_id,
                        action="lead_scored",
                        actor_type=ActorType.agent,
                        actor_name="LeadScoringAgent",
                        status="ok",
                        metadata={
                            "score": lead_run.output.lead_score,
                            "temperature": lead_run.output.lead_temperature.value,
                            "business_intent": lead_run.output.business_intent.value,
                            "priority": lead_run.output.sales_priority.value,
                        },
                    )
                    if case is not None and self._cases is not None:
                        case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

                if case is not None and self._cases is not None:
                    case = self._cases.set_lead_scoring(case=case, scoring=lead_run.output)
                    case = self._cases.set_lead_summary(
                        case=case,
                        lead_summary=(
                            f"score={lead_run.output.lead_score} "
                            f"temp={lead_run.output.lead_temperature.value} "
                            f"intent={lead_run.output.business_intent.value} "
                            f"priority={lead_run.output.sales_priority.value}"
                        ),
                    )
                    case = self._cases.touch_status(case=case, status="sales_reviewed")

        # Sales agent (company role) -> record sales decision into case + audit
        if (
            self._sales is not None
            and self._cases is not None
            and case is not None
            and self._should_route_to_sales(email=email, result=result, research=research_out)
        ):
            case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._sales, "name", "SalesAgent"))
            if self._audit is not None:
                ev = self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="sales_review_started",
                    actor_type=ActorType.orchestrator,
                    actor_name="EmailOrchestrator",
                    status="info",
                    metadata={},
                )
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

            sales_run = self._sales.run(SalesAgentInput(case=case))

            if self._audit is not None:
                ev = self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="sales_review_completed",
                    actor_type=ActorType.agent,
                    actor_name="SalesAgent",
                    status="ok" if sales_run.output is not None else "error",
                    metadata={"status": sales_run.status.value},
                )
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

            if sales_run.output is not None:
                case = self._cases.apply_sales_review(case=case, review=sales_run.output)
                case = self._cases.touch_status(case=case, status="sales_reviewed")
                if self._audit is not None:
                    ev = self._audit.log(
                        entity_type=EntityType.workflow,
                        entity_id=email.message_id,
                        action="sales_decision_recorded",
                        actor_type=ActorType.agent,
                        actor_name="SalesAgent",
                        status="ok",
                        metadata={
                            "sales_decision": sales_run.output.sales_decision.value,
                            "lead_stage": sales_run.output.lead_stage.value,
                            "confidence": sales_run.output.confidence,
                        },
                    )
                    case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

        # Professor agent (expert) -> record expert notes into case + audit
        if (
            self._prof is not None
            and self._cases is not None
            and case is not None
            and self._should_route_to_professor(email=email, result=result, research=research_out)
        ):
            case = self._cases.add_assigned_agent(case=case, agent_name=getattr(self._prof, "name", "ProfessorAgent"))
            if self._audit is not None:
                ev = self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="expert_review_started",
                    actor_type=ActorType.orchestrator,
                    actor_name="EmailOrchestrator",
                    status="info",
                    metadata={},
                )
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

            prof_run = self._prof.run(ProfessorAgentInput(case=case))

            if self._audit is not None:
                ev = self._audit.log(
                    entity_type=EntityType.workflow,
                    entity_id=email.message_id,
                    action="expert_review_completed",
                    actor_type=ActorType.agent,
                    actor_name="ProfessorAgent",
                    status="ok" if prof_run.output is not None else "error",
                    metadata={"status": prof_run.status.value},
                )
                case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

            if prof_run.output is not None:
                case = self._cases.apply_professor_review(case=case, review=prof_run.output)
                case = self._cases.touch_status(case=case, status="expert_reviewed")
                if self._audit is not None:
                    ev = self._audit.log(
                        entity_type=EntityType.workflow,
                        entity_id=email.message_id,
                        action="expert_notes_recorded",
                        actor_type=ActorType.agent,
                        actor_name="ProfessorAgent",
                        status="ok",
                        metadata={"confidence": prof_run.output.confidence},
                    )
                    case = self._cases.link_audit_event_id(case=case, event_id=ev.event_id)

        return result

    @staticmethod
    def _should_route_to_sales(*, email: EmailInput, result: AgentResult, research: ResearchAgentOutput | None) -> bool:
        if result.category in (Category.partnership, Category.sales_inquiry):
            return True
        text = ((email.subject or "") + "\n" + (email.body_text or "")).lower()
        if any(k in text for k in ["oferta", "partnerstwo", "współpraca", "wspolpraca", "wdroż", "wdroze", "implement"]):
            return True
        if research is not None:
            return True
        return False

    @staticmethod
    def _should_route_to_professor(*, email: EmailInput, result: AgentResult, research: ResearchAgentOutput | None) -> bool:
        if research is not None:
            return True
        if result.category in (Category.partnership, Category.sales_inquiry):
            return True
        text = ((email.subject or "") + "\n" + (email.body_text or "")).lower()
        if any(k in text for k in ["wdroż", "wdroze", "implement", "integrac", "strateg", "partnerstwo", "współpraca", "wspolpraca"]):
            return True
        try:
            if float(result.confidence) < 0.55:
                return True
        except Exception:
            return True
        return False

    @staticmethod
    def _should_score_lead(*, email: EmailInput, result: AgentResult) -> bool:
        if result.category in (Category.partnership, Category.sales_inquiry):
            return True
        text = ((email.subject or "") + "\n" + (email.body_text or "")).lower()
        return any(k in text for k in ["oferta", "partnerstwo", "współpraca", "wspolpraca", "wdroż", "wdroze", "implement"])

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

