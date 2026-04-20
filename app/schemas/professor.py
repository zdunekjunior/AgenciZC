from __future__ import annotations

from pydantic import BaseModel, Field


class ProfessorReview(BaseModel):
    expert_summary: str = Field(..., min_length=1)
    problem_interpretation: str = Field(..., min_length=1)
    domain_context: str = Field(..., min_length=1)
    key_risks: list[str] = Field(default_factory=list)
    key_questions: list[str] = Field(default_factory=list)
    recommended_expert_next_step: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

