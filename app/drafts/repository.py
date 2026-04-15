from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from app.domain.drafts import DraftApprovalStatus
from app.schemas.drafts import DraftRecord


class DraftNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class CreateDraftRecord:
    draft_id: str
    provider: str = "gmail"
    message_id: str | None = None
    thread_id: str | None = None
    draft_preview: str | None = None


class DraftRepository:
    def add_pending(self, *, rec: CreateDraftRecord) -> DraftRecord:
        raise NotImplementedError

    def list_by_status(self, *, status: DraftApprovalStatus) -> list[DraftRecord]:
        raise NotImplementedError

    def get(self, *, draft_id: str) -> DraftRecord:
        raise NotImplementedError

    def set_status(self, *, draft_id: str, status: DraftApprovalStatus) -> DraftRecord:
        raise NotImplementedError

    def set_last_error(self, *, draft_id: str, message: str) -> DraftRecord:
        raise NotImplementedError


class InMemoryDraftRepository(DraftRepository):
    """
    Simple in-memory store (dev/testing).
    Replace with DB-backed repository later.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, DraftRecord] = {}

    def add_pending(self, *, rec: CreateDraftRecord) -> DraftRecord:
        now = datetime.now(tz=timezone.utc)
        record = DraftRecord(
            draft_id=rec.draft_id,
            status=DraftApprovalStatus.pending_review,
            provider=rec.provider,
            message_id=rec.message_id,
            thread_id=rec.thread_id,
            created_at=now,
            updated_at=now,
            draft_preview=rec.draft_preview,
            sent_at=None,
            last_error=None,
        )
        with self._lock:
            self._items[rec.draft_id] = record
        return record

    def list_by_status(self, *, status: DraftApprovalStatus) -> list[DraftRecord]:
        with self._lock:
            items = [v for v in self._items.values() if v.status == status]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def get(self, *, draft_id: str) -> DraftRecord:
        with self._lock:
            rec = self._items.get(draft_id)
        if rec is None:
            raise DraftNotFoundError(draft_id)
        return rec

    def set_status(self, *, draft_id: str, status: DraftApprovalStatus) -> DraftRecord:
        with self._lock:
            rec = self._items.get(draft_id)
            if rec is None:
                raise DraftNotFoundError(draft_id)
            now = datetime.now(tz=timezone.utc)
            update: dict[str, object] = {"status": status, "updated_at": now}
            if status == DraftApprovalStatus.sent:
                update["sent_at"] = now
                update["last_error"] = None
            updated = rec.model_copy(update=update)
            self._items[draft_id] = updated
        return updated

    def set_last_error(self, *, draft_id: str, message: str) -> DraftRecord:
        with self._lock:
            rec = self._items.get(draft_id)
            if rec is None:
                raise DraftNotFoundError(draft_id)
            now = datetime.now(tz=timezone.utc)
            updated = rec.model_copy(update={"last_error": message, "updated_at": now})
            self._items[draft_id] = updated
        return updated

