from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agents.email_agent import EmailAgent
from app.config import Settings, get_settings
from app.integrations.gmail.service import GmailNotConfiguredError, GmailService
from app.jobs.inbox_processor import InboxProcessor
from app.schemas.jobs import ProcessInboxRequest, ProcessInboxResponse
from app.services.openai_client import OpenAIResponsesClient

router = APIRouter()
log = logging.getLogger(__name__)


def get_openai_client(settings: Settings = Depends(get_settings)) -> OpenAIResponsesClient:
    return OpenAIResponsesClient.from_settings(settings)


def get_email_agent(client: OpenAIResponsesClient = Depends(get_openai_client)) -> EmailAgent:
    return EmailAgent(client=client)


def get_gmail_service(settings: Settings = Depends(get_settings)) -> GmailService:
    try:
        return GmailService.from_settings(settings)
    except GmailNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=f"Gmail integration not configured: {exc}") from exc


def get_inbox_processor(
    gmail: GmailService = Depends(get_gmail_service),
    agent: EmailAgent = Depends(get_email_agent),
) -> InboxProcessor:
    return InboxProcessor(gmail=gmail, agent=agent)


@router.post("/process-inbox", response_model=ProcessInboxResponse)
def process_inbox(
    payload: ProcessInboxRequest,
    job: InboxProcessor = Depends(get_inbox_processor),
) -> ProcessInboxResponse:
    stats = job.process_inbox(limit=payload.limit, query=payload.query)
    log.info(
        "process_inbox finished",
        extra={
            "checked": stats.checked,
            "analyzed": stats.analyzed,
            "drafts_created": stats.drafts_created,
            "skipped": stats.skipped,
            "skipped_already_processed": stats.skipped_already_processed,
        },
    )
    return ProcessInboxResponse(
        checked=stats.checked,
        skipped_already_processed=stats.skipped_already_processed,
        analyzed=stats.analyzed,
        drafts_created=stats.drafts_created,
        skipped=stats.skipped,
        processed_message_ids=stats.processed_message_ids,
    )

