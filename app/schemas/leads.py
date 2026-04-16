from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.leads import BusinessIntent, LeadTemperature, SalesPriority


class LeadScoring(BaseModel):
    lead_score: int = Field(..., ge=0, le=100)
    lead_temperature: LeadTemperature
    business_intent: BusinessIntent
    sales_priority: SalesPriority
    recommended_followup: str = Field(..., min_length=1)
    qualification_notes: str = Field(..., min_length=1)


class LeadRecord(BaseModel):
    entity_id: str = Field(..., description="Typically email message_id")
    created_at: datetime
    scoring: LeadScoring


class LeadsListResponse(BaseModel):
    leads: list[LeadRecord]

