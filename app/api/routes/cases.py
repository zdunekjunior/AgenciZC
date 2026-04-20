from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.auth.admin_auth import require_admin_session
from app.cases.repository import InMemoryCaseRepository
from app.cases.service import CaseService
from app.cases.models import CaseContext


router = APIRouter(dependencies=[Depends(require_admin_session)])


@lru_cache(maxsize=1)
def _default_repo() -> InMemoryCaseRepository:
    return InMemoryCaseRepository()


def get_case_service() -> CaseService:
    return CaseService(repo=_default_repo())


@router.get("", response_model=list[CaseContext])
def list_cases(limit: int = 200, service: CaseService = Depends(get_case_service)) -> list[CaseContext]:
    return service.list(limit=limit)


@router.get("/{case_id}", response_model=CaseContext)
def get_case(case_id: str, service: CaseService = Depends(get_case_service)) -> CaseContext:
    case = service.get(case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case

