from __future__ import annotations

from app.leads.repository import CreateLeadRecord, LeadRepository
from app.schemas.leads import LeadRecord, LeadScoring


class LeadService:
    def __init__(self, *, repo: LeadRepository) -> None:
        self._repo = repo

    def upsert(self, *, entity_id: str, scoring: LeadScoring) -> LeadRecord:
        return self._repo.upsert(rec=CreateLeadRecord(entity_id=entity_id, scoring=scoring))

    def list(self, *, limit: int = 200) -> list[LeadRecord]:
        return self._repo.list(limit=limit)

    def get(self, *, entity_id: str) -> LeadRecord | None:
        return self._repo.get(entity_id=entity_id)

