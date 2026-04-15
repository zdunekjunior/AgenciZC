from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.api.routes.audit import get_audit_service
from app.api.routes.drafts import get_draft_service
from app.audit.service import AuditLogService
from app.domain.audit import ActorType, EntityType
from app.drafts.service import DraftApprovalService
from app.orchestrator.email_orchestrator import EmailOrchestrator
from app.domain.enums import RecommendedAction
from app.integrations.gmail.service import GmailService
from app.schemas.email import AgentResult

log = logging.getLogger(__name__)


LABEL_PROCESSED = "AI/Processed"
LABEL_DRAFT_CREATED = "AI/DraftCreated"
LABEL_SKIPPED = "AI/Skipped"


@dataclass(frozen=True)
class InboxProcessStats:
    checked: int
    skipped_already_processed: int
    analyzed: int
    drafts_created: int
    skipped: int
    processed_message_ids: list[str]


def _get_label_ids(message: dict[str, Any]) -> set[str]:
    ids = message.get("labelIds") or []
    if isinstance(ids, list):
        return {str(x) for x in ids if x}
    return set()


class InboxProcessor:
    """
    Polling inbox processor (no background workers).
    """

    def __init__(self, *, gmail: GmailService, agent: EmailOrchestrator, drafts: DraftApprovalService | None = None) -> None:
        self._gmail = gmail
        self._agent = agent
        self._drafts = drafts or get_draft_service()
        self._audit: AuditLogService = get_audit_service()

    def process_inbox(self, *, limit: int = 10, query: str | None = None) -> InboxProcessStats:
        if limit < 1:
            limit = 1
        if limit > 50:
            limit = 50

        processed_label_id = self._gmail.ensure_label(name=LABEL_PROCESSED)

        listing = self._gmail.list_message_metadatas(limit=limit, query=query)

        checked = 0
        skipped_already_processed = 0
        analyzed = 0
        drafts_created = 0
        skipped = 0
        processed_ids: list[str] = []

        for meta in listing:
            mid = meta.get("id")
            if not mid:
                continue
            checked += 1

            label_ids = _get_label_ids(meta)
            if processed_label_id in label_ids:
                skipped_already_processed += 1
                continue

            try:
                msg = self._gmail.fetch_message(message_id=mid)
                email_input = self._gmail.fetch_email_input(message_id=mid)
            except Exception:  # noqa: BLE001
                log.exception("Failed to fetch message/thread for processing")
                continue

            result: AgentResult = self._agent.handle_email(email_input)
            analyzed += 1

            self._audit.log(
                entity_type=EntityType.email,
                entity_id=mid,
                action="email_analyzed",
                actor_type=ActorType.system,
                actor_name="jobs.process_inbox",
                status="ok",
                metadata={"thread_id": msg.get("threadId")},
            )

            action = result.recommended_action
            create_draft = action != RecommendedAction.ignore and bool(result.draft_reply and result.draft_reply.strip())

            if create_draft:
                try:
                    draft_id = self._gmail.create_reply_draft(original_message=msg, draft_reply=result.draft_reply)
                    drafts_created += 1
                    self._audit.log(
                        entity_type=EntityType.draft,
                        entity_id=draft_id,
                        action="draft_created",
                        actor_type=ActorType.system,
                        actor_name="GmailService",
                        status="ok",
                        metadata={"message_id": mid, "thread_id": msg.get("threadId")},
                    )
                    self._drafts.register_new_draft(
                        draft_id=draft_id,
                        provider="gmail",
                        message_id=mid,
                        thread_id=msg.get("threadId"),
                        draft_body=result.draft_reply,
                    )
                    self._audit.log(
                        entity_type=EntityType.draft,
                        entity_id=draft_id,
                        action="draft_moved_to_pending_review",
                        actor_type=ActorType.system,
                        actor_name="DraftApprovalService",
                        status="ok",
                        metadata={},
                    )
                    self._gmail.apply_labels(message_id=mid, label_names=[LABEL_PROCESSED, LABEL_DRAFT_CREATED])
                except Exception:  # noqa: BLE001
                    log.exception("Draft creation failed; marking as skipped")
                    skipped += 1
                    self._gmail.apply_labels(message_id=mid, label_names=[LABEL_PROCESSED, LABEL_SKIPPED])
            else:
                skipped += 1
                self._gmail.apply_labels(message_id=mid, label_names=[LABEL_PROCESSED, LABEL_SKIPPED])

            processed_ids.append(mid)

        return InboxProcessStats(
            checked=checked,
            skipped_already_processed=skipped_already_processed,
            analyzed=analyzed,
            drafts_created=drafts_created,
            skipped=skipped,
            processed_message_ids=processed_ids,
        )

