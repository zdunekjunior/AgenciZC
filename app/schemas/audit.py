from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

from app.domain.audit import ActorType, EntityType

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AuditEvent(BaseModel):
    event_id: NonEmptyStr
    timestamp: datetime
    entity_type: EntityType
    entity_id: NonEmptyStr
    action: NonEmptyStr
    actor_type: ActorType
    actor_name: NonEmptyStr
    status: str = Field(..., description="ok|error|skipped|info")
    metadata: dict = Field(default_factory=dict)


class AuditEventsResponse(BaseModel):
    events: list[AuditEvent]

