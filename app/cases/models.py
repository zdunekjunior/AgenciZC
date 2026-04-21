from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

from app.schemas.leads import LeadScoring

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CaseSourceType(str):
    """
    Foundation source marker.
    Keep it a string subtype to avoid migration pain.
    """


class CaseStatus(str):
    """
    Foundation status marker.
    Examples: open|analyzed|research_added|lead_added|draft_linked|closed
    """


class CaseNote(BaseModel):
    timestamp: datetime
    author: str = Field(..., description="Agent/orchestrator/human identifier")
    kind: str = Field(..., description="research|sales|dev|finance|ops|general")
    text: str = Field(..., min_length=1)
    metadata: dict = Field(default_factory=dict)


class CaseDecision(BaseModel):
    timestamp: datetime
    decided_by: str = Field(..., description="Agent/orchestrator/human identifier")
    decision: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    metadata: dict = Field(default_factory=dict)


class CaseContext(BaseModel):
    """
    Shared case file for multi-agent collaboration.

    This is the integration foundation: agents write into a shared context,
    while public APIs can remain backward compatible.
    """

    # Identity
    case_id: NonEmptyStr

    # Source
    source_type: str = Field(..., description="api|gmail|job|other")
    message_id: NonEmptyStr
    thread_id: str | None = None
    from_email: str | None = None
    subject: str | None = None

    created_at: datetime
    updated_at: datetime

    # Workflow
    current_status: str = Field(default="open", description="open|analyzed|research_added|lead_added|draft_linked|closed")
    assigned_agents: list[str] = Field(default_factory=list)

    # Gatekeeper decision (Secretary/gatekeeper layer)
    inbox_decision: str | None = Field(default=None, description="reply_needed|review_only|ignore")
    inbox_decision_reason: str | None = None
    draft_policy: str | None = Field(default=None, description="draft_only_for_reply_needed")
    draft_skipped_reason: str | None = None

    # Cross-agent shared artifacts (summaries)
    notes: list[CaseNote] = Field(default_factory=list)
    research_summary: str | None = None
    lead_summary: str | None = None
    lead_scoring: LeadScoring | None = None
    development_notes: list[str] = Field(default_factory=list)
    finance_notes: list[str] = Field(default_factory=list)

    # Sales layer (company agent)
    sales_decision: str | None = None
    lead_stage: str | None = None
    recommended_next_action: str | None = None
    follow_up_plan: list[str] = Field(default_factory=list)
    sales_notes: str | None = None
    sales_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Expert layer (ProfessorAgent)
    expert_summary: str | None = None
    problem_interpretation: str | None = None
    domain_context: str | None = None
    key_risks: list[str] = Field(default_factory=list)
    key_questions: list[str] = Field(default_factory=list)
    recommended_expert_next_step: str | None = None
    expert_notes: str | None = None
    expert_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Links
    draft_ids: list[str] = Field(default_factory=list, description="Provider draft ids (e.g. Gmail draft_id)")
    audit_event_ids: list[str] = Field(default_factory=list, description="AuditEvent.event_id references")

