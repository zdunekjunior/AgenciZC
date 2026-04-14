from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GmailMessageRequest(BaseModel):
    message_id: NonEmptyStr = Field(..., description="Gmail message id")


class GmailDraftResult(BaseModel):
    status: str = Field(..., description="created|skipped|error")
    draft_id: str | None = None
    error: str | None = None
    reason: str | None = Field(default=None, description="Reason for skipping draft (if status=skipped)")


class GmailAnalyzeResult(BaseModel):
    analysis: dict = Field(..., description="AgentResult payload")
    gmail_message_id: str
    gmail_thread_id: str | None = None


class GmailAnalyzeAndDraftResult(BaseModel):
    analysis: dict = Field(..., description="AgentResult payload")
    gmail_message_id: str
    gmail_thread_id: str | None = None
    draft: GmailDraftResult
    label_applied: list[str] = Field(default_factory=list)
    action_taken: str = Field(..., description="draft_created|skipped")


class GmailMessageListItem(BaseModel):
    message_id: str
    thread_id: str | None = None
    subject: str | None = None
    from_email: str | None = None
    snippet: str | None = None
    internal_date: datetime | None = None


class GmailMessagesListResponse(BaseModel):
    messages: list[GmailMessageListItem]

