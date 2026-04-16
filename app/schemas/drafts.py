from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

from app.domain.drafts import DraftApprovalStatus
from app.schemas.leads import LeadScoring

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DraftRecord(BaseModel):
    draft_id: NonEmptyStr = Field(..., description="Draft id (e.g., Gmail draft id)")
    status: DraftApprovalStatus = Field(default=DraftApprovalStatus.pending_review)
    provider: str = Field(default="gmail", description="Draft provider identifier")
    message_id: str | None = Field(default=None, description="Original message id (provider-specific)")
    thread_id: str | None = Field(default=None, description="Thread id (provider-specific)")
    created_at: datetime
    updated_at: datetime
    draft_preview: str | None = Field(default=None, description="Short preview of draft body (optional)")
    sent_at: datetime | None = Field(default=None, description="When the draft was sent (if status=sent)")
    last_error: str | None = Field(default=None, description="Last send error message (if any)")
    lead_scoring: LeadScoring | None = Field(default=None, description="Lead scoring snapshot (optional)")


class PendingDraftsResponse(BaseModel):
    drafts: list[DraftRecord]


class DraftActionResponse(BaseModel):
    draft: DraftRecord

