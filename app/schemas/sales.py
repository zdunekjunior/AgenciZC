from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SalesDecision(str, Enum):
    qualified = "qualified"
    disqualified = "disqualified"
    needs_info = "needs_info"
    follow_up = "follow_up"
    skip = "skip"


class LeadStage(str, Enum):
    new = "new"
    qualified = "qualified"
    meeting_proposed = "meeting_proposed"
    meeting_scheduled = "meeting_scheduled"
    proposal = "proposal"
    negotiation = "negotiation"
    nurture = "nurture"
    won = "won"
    lost = "lost"


class SalesReview(BaseModel):
    sales_decision: SalesDecision
    lead_stage: LeadStage
    recommended_next_action: str = Field(..., min_length=1)
    follow_up_plan: list[str] = Field(default_factory=list)
    sales_notes: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

