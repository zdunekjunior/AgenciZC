from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from app.audit.repository import InMemoryAuditRepository
from app.audit.service import AuditLogService
from app.schemas.audit import AuditEventsResponse

router = APIRouter()


@lru_cache(maxsize=1)
def _default_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


def get_audit_service() -> AuditLogService:
    return AuditLogService(repo=_default_repo())


@router.get("/events", response_model=AuditEventsResponse)
def list_events(limit: int = 200, service: AuditLogService = Depends(get_audit_service)) -> AuditEventsResponse:
    return AuditEventsResponse(events=service.list_events(limit=limit))


@router.get("/events/{entity_id}", response_model=AuditEventsResponse)
def list_events_for_entity(entity_id: str, limit: int = 200, service: AuditLogService = Depends(get_audit_service)) -> AuditEventsResponse:
    return AuditEventsResponse(events=service.list_events_for_entity(entity_id=entity_id, limit=limit))

