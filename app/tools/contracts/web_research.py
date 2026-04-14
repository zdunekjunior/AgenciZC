from __future__ import annotations

from pydantic import BaseModel, Field


class WebResearchInput(BaseModel):
    query: str = Field(..., min_length=3, max_length=300)


class WebResearchOutput(BaseModel):
    summary: str = Field(..., min_length=1)
    sources: list[str] = Field(default_factory=list, description="URLs or identifiers (future)")

