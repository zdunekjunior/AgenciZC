from __future__ import annotations

from app.audit.repository import AuditRepository, CreateAuditEvent
from app.domain.audit import ActorType, EntityType
from app.schemas.audit import AuditEvent


class AuditLogService:
    def __init__(self, *, repo: AuditRepository) -> None:
        self._repo = repo

    def log(
        self,
        *,
        entity_type: EntityType,
        entity_id: str,
        action: str,
        actor_type: ActorType,
        actor_name: str,
        status: str = "info",
        metadata: dict | None = None,
    ) -> AuditEvent:
        return self._repo.add(
            ev=CreateAuditEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_type=actor_type,
                actor_name=actor_name,
                status=status,
                metadata=metadata or {},
            )
        )

    def list_events(self, *, limit: int = 200) -> list[AuditEvent]:
        return self._repo.list(limit=limit)

    def list_events_for_entity(self, *, entity_id: str, limit: int = 200) -> list[AuditEvent]:
        return self._repo.list_for_entity(entity_id=entity_id, limit=limit)

