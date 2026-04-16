from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from app.schemas.leads import LeadRecord, LeadScoring


@dataclass(frozen=True)
class CreateLeadRecord:
    entity_id: str
    scoring: LeadScoring


class LeadRepository:
    def upsert(self, *, rec: CreateLeadRecord) -> LeadRecord:
        raise NotImplementedError

    def list(self, *, limit: int = 200) -> list[LeadRecord]:
        raise NotImplementedError

    def get(self, *, entity_id: str) -> LeadRecord | None:
        raise NotImplementedError


class InMemoryLeadRepository(LeadRepository):
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, LeadRecord] = {}

    def upsert(self, *, rec: CreateLeadRecord) -> LeadRecord:
        now = datetime.now(tz=timezone.utc)
        record = LeadRecord(entity_id=rec.entity_id, created_at=now, scoring=rec.scoring)
        with self._lock:
            self._items[rec.entity_id] = record
        return record

    def list(self, *, limit: int = 200) -> list[LeadRecord]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            items = list(self._items.values())
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[:limit]

    def get(self, *, entity_id: str) -> LeadRecord | None:
        with self._lock:
            return self._items.get(entity_id)

