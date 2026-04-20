from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OutputVerdict(str):
    """
    Lightweight verdict marker for future learning loops.
    Use string values to keep storage/simple filtering easy.
    """


class HumanCorrection(BaseModel):
    timestamp: datetime
    actor: str = Field(..., description="human identifier")
    field: str = Field(..., description="What was corrected (e.g., draft_reply, lead_scoring, category)")
    before: str | None = None
    after: str | None = None
    note: str = ""


class CaseOutcome(BaseModel):
    """
    Post-case summary for learning/analytics (no model training).
    """

    case_id: str
    timestamp: datetime
    outcome: str = Field(..., description="won|lost|resolved|stale|other")
    reason: str = Field(..., min_length=1)
    metadata: dict = Field(default_factory=dict)


class Playbook(BaseModel):
    """
    Reusable instructions distilled from successful cases.
    """

    playbook_id: str
    created_at: datetime
    updated_at: datetime
    title: str = Field(..., min_length=1)
    applies_when: str = Field(..., min_length=1, description="Rule of thumb / trigger conditions")
    steps: list[str] = Field(default_factory=list)
    example_inputs: list[str] = Field(default_factory=list)
    example_outputs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class FeedbackMemoryItem(BaseModel):
    """
    A single feedback unit for future retrieval-based improvements (RAG-like),
    not training. Can be stored alongside audit log references.
    """

    memory_id: str
    created_at: datetime
    case_id: str
    agent_name: str
    topic: str = Field(..., min_length=1)
    signal: str = Field(..., min_length=1, description="What should the system remember")
    examples: list[str] = Field(default_factory=list)
    verdict: str = Field(default="approved", description="approved|rejected|needs_review")
    corrections: list[HumanCorrection] = Field(default_factory=list)

