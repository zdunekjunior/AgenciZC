from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessInboxRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    query: str | None = Field(default=None, description="Optional Gmail search query (e.g. 'in:inbox newer_than:7d')")


class ProcessInboxResponse(BaseModel):
    checked: int
    skipped_already_processed: int
    analyzed: int
    drafts_created: int
    skipped: int
    processed_message_ids: list[str]

