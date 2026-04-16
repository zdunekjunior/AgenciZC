from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from app.auth.admin_auth import require_admin_session
from app.leads.repository import InMemoryLeadRepository
from app.leads.service import LeadService
from app.schemas.leads import LeadRecord, LeadsListResponse

router = APIRouter(dependencies=[Depends(require_admin_session)])


@lru_cache(maxsize=1)
def _default_repo() -> InMemoryLeadRepository:
    return InMemoryLeadRepository()


def get_lead_service() -> LeadService:
    return LeadService(repo=_default_repo())


@router.get("", response_model=LeadsListResponse)
def list_leads(limit: int = 200, service: LeadService = Depends(get_lead_service)) -> LeadsListResponse:
    return LeadsListResponse(leads=service.list(limit=limit))


@router.get("/{entity_id}", response_model=LeadRecord)
def get_lead(entity_id: str, service: LeadService = Depends(get_lead_service)) -> LeadRecord:
    rec = service.get(entity_id=entity_id)
    if rec is None:
        # FastAPI will turn this into 404 if we raise
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="lead not found")
    return rec

