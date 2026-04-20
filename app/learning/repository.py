from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.learning.models import FeedbackMemoryItem, HumanCorrection, Playbook


@dataclass(frozen=True)
class CreatePlaybookRequest:
    title: str
    applies_when: str
    steps: list[str]
    tags: list[str] | None = None


@dataclass(frozen=True)
class CreateFeedbackItemRequest:
    case_id: str
    agent_name: str
    topic: str
    signal: str
    examples: list[str] | None = None
    verdict: str = "approved"
    corrections: list[HumanCorrection] | None = None


class LearningRepository:
    def add_playbook(self, *, req: CreatePlaybookRequest) -> Playbook:
        raise NotImplementedError

    def list_playbooks(self, *, limit: int = 200) -> list[Playbook]:
        raise NotImplementedError

    def add_feedback(self, *, req: CreateFeedbackItemRequest) -> FeedbackMemoryItem:
        raise NotImplementedError

    def list_feedback(self, *, case_id: str | None = None, limit: int = 200) -> list[FeedbackMemoryItem]:
        raise NotImplementedError


class InMemoryLearningRepository(LearningRepository):
    """
    Foundation repository for future "learning without training".
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._playbooks: dict[str, Playbook] = {}
        self._feedback: dict[str, FeedbackMemoryItem] = {}

    def add_playbook(self, *, req: CreatePlaybookRequest) -> Playbook:
        now = datetime.now(tz=timezone.utc)
        pid = uuid4().hex
        pb = Playbook(
            playbook_id=pid,
            created_at=now,
            updated_at=now,
            title=req.title,
            applies_when=req.applies_when,
            steps=req.steps,
            tags=req.tags or [],
        )
        with self._lock:
            self._playbooks[pid] = pb
        return pb

    def list_playbooks(self, *, limit: int = 200) -> list[Playbook]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            items = list(self._playbooks.values())
        items.sort(key=lambda x: x.updated_at, reverse=True)
        return items[:limit]

    def add_feedback(self, *, req: CreateFeedbackItemRequest) -> FeedbackMemoryItem:
        now = datetime.now(tz=timezone.utc)
        mid = uuid4().hex
        item = FeedbackMemoryItem(
            memory_id=mid,
            created_at=now,
            case_id=req.case_id,
            agent_name=req.agent_name,
            topic=req.topic,
            signal=req.signal,
            examples=req.examples or [],
            verdict=req.verdict,
            corrections=req.corrections or [],
        )
        with self._lock:
            self._feedback[mid] = item
        return item

    def list_feedback(self, *, case_id: str | None = None, limit: int = 200) -> list[FeedbackMemoryItem]:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000
        with self._lock:
            items = list(self._feedback.values())
        if case_id:
            items = [i for i in items if i.case_id == case_id]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

