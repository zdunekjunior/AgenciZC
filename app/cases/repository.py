from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.cases.models import CaseContext, NonEmptyStr


@dataclass(frozen=True)
class CreateCaseRequest:
    source_type: str
    message_id: NonEmptyStr
    thread_id: str | None
    from_email: str | None
    subject: str | None


class CaseRepository:
    def create(self, *, req: CreateCaseRequest) -> CaseContext:
        raise NotImplementedError

    def get(self, *, case_id: str) -> CaseContext | None:
        raise NotImplementedError

    def upsert(self, *, ctx: CaseContext) -> CaseContext:
        raise NotImplementedError

    def get_by_message_id(self, *, message_id: str) -> CaseContext | None:
        raise NotImplementedError

    def list(self, *, limit: int = 200) -> list[CaseContext]:
        raise NotImplementedError


class InMemoryCaseRepository(CaseRepository):
    """
    In-memory case store (process-local).
    Replace with DB later.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, CaseContext] = {}
        self._by_message_id: dict[str, str] = {}

    def create(self, *, req: CreateCaseRequest) -> CaseContext:
        now = datetime.now(tz=timezone.utc)
        case_id = uuid4().hex
        ctx = CaseContext(
            case_id=case_id,
            source_type=req.source_type,
            message_id=req.message_id,
            thread_id=req.thread_id,
            from_email=req.from_email,
            subject=req.subject,
            created_at=now,
            updated_at=now,
            current_status="open",
            assigned_agents=[],
            notes=[],
            research_summary=None,
            lead_summary=None,
            lead_scoring=None,
            development_notes=[],
            finance_notes=[],
            sales_decision=None,
            lead_stage=None,
            recommended_next_action=None,
            follow_up_plan=[],
            sales_notes=None,
            sales_confidence=None,
            expert_summary=None,
            problem_interpretation=None,
            domain_context=None,
            key_risks=[],
            key_questions=[],
            recommended_expert_next_step=None,
            expert_notes=None,
            expert_confidence=None,
            draft_ids=[],
            audit_event_ids=[],
        )
        with self._lock:
            self._items[case_id] = ctx
            self._by_message_id[str(req.message_id)] = case_id
        return ctx

    def get(self, *, case_id: str) -> CaseContext | None:
        with self._lock:
            return self._items.get(case_id)

    def upsert(self, *, ctx: CaseContext) -> CaseContext:
        now = datetime.now(tz=timezone.utc)
        updated = ctx.model_copy(update={"updated_at": now})
        with self._lock:
            self._items[ctx.case_id] = updated
            self._by_message_id[str(updated.message_id)] = updated.case_id
        return updated

    def get_by_message_id(self, *, message_id: str) -> CaseContext | None:
        mid = (message_id or "").strip()
        if not mid:
            return None
        with self._lock:
            cid = self._by_message_id.get(mid)
            if not cid:
                return None
            return self._items.get(cid)

    def list(self, *, limit: int = 200) -> list[CaseContext]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            items = list(self._items.values())
        items.sort(key=lambda c: c.updated_at, reverse=True)
        return items[:limit]

