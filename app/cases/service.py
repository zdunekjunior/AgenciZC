from __future__ import annotations

from datetime import datetime, timezone

from app.cases.models import CaseContext, CaseNote
from app.cases.repository import CaseRepository, CreateCaseRequest
from app.schemas.email import EmailInput
from app.schemas.leads import LeadScoring
from app.schemas.professor import ProfessorReview
from app.schemas.sales import SalesReview


class CaseService:
    def __init__(self, *, repo: CaseRepository) -> None:
        self._repo = repo

    def get(self, *, case_id: str) -> CaseContext | None:
        return self._repo.get(case_id=case_id)

    def get_by_message_id(self, *, message_id: str) -> CaseContext | None:
        return self._repo.get_by_message_id(message_id=message_id)

    def list(self, *, limit: int = 200) -> list[CaseContext]:
        return self._repo.list(limit=limit)

    def get_or_create_from_email(self, *, email: EmailInput, source_type: str) -> CaseContext:
        existing = self._repo.get_by_message_id(message_id=email.message_id)
        if existing is not None:
            # Keep latest basic headers for convenience.
            updated = existing.model_copy(
                update={
                    "thread_id": email.thread_id,
                    "from_email": str(email.sender) if email.sender else existing.from_email,
                    "subject": email.subject or existing.subject,
                    "source_type": existing.source_type or source_type,
                }
            )
            return self._repo.upsert(ctx=updated)

        return self._repo.create(
            req=CreateCaseRequest(
                source_type=source_type,
                message_id=email.message_id,
                thread_id=email.thread_id,
                from_email=str(email.sender) if email.sender else None,
                subject=email.subject,
            )
        )

    def touch_status(self, *, case: CaseContext, status: str) -> CaseContext:
        return self._repo.upsert(ctx=case.model_copy(update={"current_status": status}))

    def add_assigned_agent(self, *, case: CaseContext, agent_name: str) -> CaseContext:
        agent_name = (agent_name or "").strip()
        if not agent_name:
            return case
        if agent_name in case.assigned_agents:
            return case
        return self._repo.upsert(ctx=case.model_copy(update={"assigned_agents": [*case.assigned_agents, agent_name]}))

    def add_note(self, *, case: CaseContext, author: str, kind: str, text: str, metadata: dict | None = None) -> CaseContext:
        now = datetime.now(tz=timezone.utc)
        note = CaseNote(timestamp=now, author=author, kind=kind, text=text, metadata=metadata or {})
        return self._repo.upsert(ctx=case.model_copy(update={"notes": [*case.notes, note]}))

    def set_research_summary(self, *, case: CaseContext, research_summary: str) -> CaseContext:
        return self._repo.upsert(ctx=case.model_copy(update={"research_summary": research_summary}))

    def set_lead_summary(self, *, case: CaseContext, lead_summary: str) -> CaseContext:
        return self._repo.upsert(ctx=case.model_copy(update={"lead_summary": lead_summary}))

    def set_lead_scoring(self, *, case: CaseContext, scoring: LeadScoring) -> CaseContext:
        return self._repo.upsert(ctx=case.model_copy(update={"lead_scoring": scoring}))

    def link_draft_id(self, *, case: CaseContext, draft_id: str) -> CaseContext:
        did = (draft_id or "").strip()
        if not did:
            return case
        if did in case.draft_ids:
            return case
        return self._repo.upsert(ctx=case.model_copy(update={"draft_ids": [*case.draft_ids, did]}))

    def link_audit_event_id(self, *, case: CaseContext, event_id: str) -> CaseContext:
        eid = (event_id or "").strip()
        if not eid:
            return case
        if eid in case.audit_event_ids:
            return case
        return self._repo.upsert(ctx=case.model_copy(update={"audit_event_ids": [*case.audit_event_ids, eid]}))

    def apply_sales_review(self, *, case: CaseContext, review: SalesReview) -> CaseContext:
        return self._repo.upsert(
            ctx=case.model_copy(
                update={
                    "sales_decision": review.sales_decision.value,
                    "lead_stage": review.lead_stage.value,
                    "recommended_next_action": review.recommended_next_action,
                    "follow_up_plan": review.follow_up_plan,
                    "sales_notes": review.sales_notes,
                    "sales_confidence": review.confidence,
                }
            )
        )

    def apply_professor_review(self, *, case: CaseContext, review: ProfessorReview) -> CaseContext:
        return self._repo.upsert(
            ctx=case.model_copy(
                update={
                    "expert_summary": review.expert_summary,
                    "problem_interpretation": review.problem_interpretation,
                    "domain_context": review.domain_context,
                    "key_risks": review.key_risks,
                    "key_questions": review.key_questions,
                    "recommended_expert_next_step": review.recommended_expert_next_step,
                    "expert_notes": review.expert_summary,
                    "expert_confidence": review.confidence,
                }
            )
        )

