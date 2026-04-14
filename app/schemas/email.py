from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, StringConstraints
from typing_extensions import Annotated

from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnalyzeEmailRequest(BaseModel):
    """
    Public API request model (Swagger-friendly).
    """

    subject: str | None = Field(default=None)
    from_email: EmailStr = Field(..., description="Sender email address")
    to_email: EmailStr = Field(..., description="Recipient email address")
    body: NonEmptyStr = Field(..., description="Email body (plain text)")
    thread_context: list[str] = Field(default_factory=list, description="Previous messages in the thread (plain text)")
    message_id: str | None = Field(default=None, description="Optional id for testing; generated if missing")


class EmailInput(BaseModel):
    """
    Input contract for the agent.

    Designed to map cleanly to Gmail payload later (messageId/threadId/from/to/cc/bcc/etc.).
    """

    message_id: NonEmptyStr = Field(..., description="Client-side or future Gmail message id")
    thread_id: str | None = Field(default=None, description="Optional thread id (future Gmail)")
    subject: str | None = Field(default=None)
    sender: EmailStr | None = Field(default=None)
    recipients: list[EmailStr] = Field(default_factory=list)
    received_at: datetime | None = Field(default=None)
    body_text: NonEmptyStr = Field(..., description="Plain text email body")
    thread_context: list[str] = Field(default_factory=list, description="Thread context (plain text)")

class AgentResult(BaseModel):
    category: Category = Field(default=Category.other)
    priority: Priority = Field(default=Priority.medium)
    summary: NonEmptyStr
    needs_human_approval: bool = Field(default=True)
    recommended_action: RecommendedAction = Field(default=RecommendedAction.draft_for_review)
    draft_reply: str = Field(default="", description="Draft reply text (may be empty)")
    reasoning_notes: str = Field(default="", description="Short, business-safe justification (no hidden reasoning).")
    suggested_tool: SuggestedTool = Field(default=SuggestedTool.none)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentResultPartial(BaseModel):
    """
    Lenient model to accept partial/invalid model output and normalize it later.
    """

    category: Any | None = None
    priority: Any | None = None
    summary: Any | None = None
    needs_human_approval: Any | None = None
    recommended_action: Any | None = None
    draft_reply: Any | None = None
    reasoning_notes: Any | None = None
    suggested_tool: Any | None = None
    confidence: Any | None = None

