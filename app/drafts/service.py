from __future__ import annotations

from app.domain.drafts import DraftApprovalStatus
from app.drafts.repository import CreateDraftRecord, DraftNotFoundError, DraftRepository
from app.schemas.drafts import DraftRecord


class DraftInvalidStateError(RuntimeError):
    pass


class DraftApprovalService:
    def __init__(self, *, repo: DraftRepository) -> None:
        self._repo = repo

    def register_new_draft(
        self,
        *,
        draft_id: str,
        provider: str = "gmail",
        message_id: str | None = None,
        thread_id: str | None = None,
        draft_body: str | None = None,
    ) -> DraftRecord:
        preview = None
        if draft_body:
            preview = (draft_body.strip().replace("\n", " ")[:240] or None)
        return self._repo.add_pending(
            rec=CreateDraftRecord(
                draft_id=draft_id,
                provider=provider,
                message_id=message_id,
                thread_id=thread_id,
                draft_preview=preview,
            )
        )

    def list_pending(self) -> list[DraftRecord]:
        return self._repo.list_by_status(status=DraftApprovalStatus.pending_review)

    def approve(self, *, draft_id: str) -> DraftRecord:
        # Ready for future "send" step: approved can later trigger provider send.
        return self._repo.set_status(draft_id=draft_id, status=DraftApprovalStatus.approved)

    def reject(self, *, draft_id: str) -> DraftRecord:
        return self._repo.set_status(draft_id=draft_id, status=DraftApprovalStatus.rejected)

    def mark_sent(self, *, draft_id: str) -> DraftRecord:
        return self._repo.set_status(draft_id=draft_id, status=DraftApprovalStatus.sent)

    def set_send_error(self, *, draft_id: str, message: str) -> DraftRecord:
        return self._repo.set_last_error(draft_id=draft_id, message=message)

    def get(self, *, draft_id: str) -> DraftRecord:
        return self._repo.get(draft_id=draft_id)

    def ensure_sendable(self, *, draft_id: str) -> DraftRecord:
        rec = self.get(draft_id=draft_id)
        if rec.status != DraftApprovalStatus.approved:
            raise DraftInvalidStateError(f"Draft is not approved (current status: {rec.status.value})")
        return rec

    @staticmethod
    def is_not_found(exc: Exception) -> bool:
        return isinstance(exc, DraftNotFoundError)

    @staticmethod
    def is_invalid_state(exc: Exception) -> bool:
        return isinstance(exc, DraftInvalidStateError)

