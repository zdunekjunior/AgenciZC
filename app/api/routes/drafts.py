from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.domain.drafts import DraftApprovalStatus
from app.drafts.repository import InMemoryDraftRepository
from app.drafts.service import DraftApprovalService
from app.integrations.gmail.service import GmailNotConfiguredError, GmailService
from app.config import Settings, get_settings
from app.schemas.drafts import DraftActionResponse, PendingDraftsResponse

router = APIRouter()


@lru_cache(maxsize=1)
def _default_repo() -> InMemoryDraftRepository:
    # Singleton in-memory store (process-local).
    return InMemoryDraftRepository()


def get_draft_service() -> DraftApprovalService:
    return DraftApprovalService(repo=_default_repo())


def get_gmail_service_optional(settings: Settings = Depends(get_settings)) -> GmailService | None:
    try:
        return GmailService.from_settings(settings)
    except GmailNotConfiguredError as exc:
        return None


@router.get("/pending", response_model=PendingDraftsResponse)
def list_pending_drafts(service: DraftApprovalService = Depends(get_draft_service)) -> PendingDraftsResponse:
    return PendingDraftsResponse(drafts=service.list_pending())


@router.post("/{draft_id}/approve", response_model=DraftActionResponse)
def approve_draft(draft_id: str, service: DraftApprovalService = Depends(get_draft_service)) -> DraftActionResponse:
    try:
        rec = service.approve(draft_id=draft_id)
    except Exception as exc:  # noqa: BLE001
        if service.is_not_found(exc):
            raise HTTPException(status_code=404, detail="draft not found") from exc
        raise
    return DraftActionResponse(draft=rec)


@router.post("/{draft_id}/reject", response_model=DraftActionResponse)
def reject_draft(draft_id: str, service: DraftApprovalService = Depends(get_draft_service)) -> DraftActionResponse:
    try:
        rec = service.reject(draft_id=draft_id)
    except Exception as exc:  # noqa: BLE001
        if service.is_not_found(exc):
            raise HTTPException(status_code=404, detail="draft not found") from exc
        raise
    return DraftActionResponse(draft=rec)


@router.post("/{draft_id}/send", response_model=DraftActionResponse)
def send_draft(
    draft_id: str,
    service: DraftApprovalService = Depends(get_draft_service),
    gmail: GmailService | None = Depends(get_gmail_service_optional),
) -> DraftActionResponse:
    try:
        rec = service.ensure_sendable(draft_id=draft_id)
    except Exception as exc:  # noqa: BLE001
        if service.is_not_found(exc):
            raise HTTPException(status_code=404, detail="draft not found") from exc
        if service.is_invalid_state(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise

    if rec.provider != "gmail":
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {rec.provider}")
    if gmail is None:
        raise HTTPException(status_code=503, detail="Gmail integration not configured")

    try:
        gmail.send_draft(draft_id=rec.draft_id)
    except Exception as exc:  # noqa: BLE001
        # Keep status unchanged; store error for audit/debug.
        service.set_send_error(draft_id=rec.draft_id, message=str(exc))
        raise HTTPException(status_code=502, detail="Failed to send draft (see server logs)") from exc

    sent = service.mark_sent(draft_id=rec.draft_id)
    return DraftActionResponse(draft=sent)


@router.get("/statuses")
def list_statuses() -> dict[str, list[str]]:
    # Dev helper: expose allowed statuses
    return {"statuses": [s.value for s in DraftApprovalStatus]}

