from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.domain.audit import ActorType, EntityType
from app.schemas.audit import AuditEvent


@dataclass(frozen=True)
class CreateAuditEvent:
    entity_type: EntityType
    entity_id: str
    action: str
    actor_type: ActorType
    actor_name: str
    status: str
    metadata: dict


class AuditRepository:
    def add(self, *, ev: CreateAuditEvent) -> AuditEvent:
        raise NotImplementedError

    def list(self, *, limit: int = 200) -> list[AuditEvent]:
        raise NotImplementedError

    def list_for_entity(self, *, entity_id: str, limit: int = 200) -> list[AuditEvent]:
        raise NotImplementedError


class InMemoryAuditRepository(AuditRepository):
    """
    In-memory event store (process-local). Replace with DB later.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[AuditEvent] = []

    def add(self, *, ev: CreateAuditEvent) -> AuditEvent:
        now = datetime.now(tz=timezone.utc)
        event = AuditEvent(
            event_id=uuid4().hex,
            timestamp=now,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            action=ev.action,
            actor_type=ev.actor_type,
            actor_name=ev.actor_name,
            status=ev.status,
            metadata=ev.metadata or {},
        )
        with self._lock:
            self._events.append(event)
        return event

    def list(self, *, limit: int = 200) -> list[AuditEvent]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            items = list(self._events[-limit:])
        return list(reversed(items))

    def list_for_entity(self, *, entity_id: str, limit: int = 200) -> list[AuditEvent]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            matched = [e for e in self._events if e.entity_id == entity_id]
            items = matched[-limit:]
        return list(reversed(items))

