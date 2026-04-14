from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.agents.email_agent import EmailAgent
from app.config import Settings, get_settings
from app.schemas.email import AgentResult, AnalyzeEmailRequest, EmailInput
from app.services.openai_client import OpenAIResponsesClient

router = APIRouter()
log = logging.getLogger(__name__)


def get_openai_client(settings: Settings = Depends(get_settings)) -> OpenAIResponsesClient:
    return OpenAIResponsesClient.from_settings(settings)


def get_email_agent(client: OpenAIResponsesClient = Depends(get_openai_client)) -> EmailAgent:
    return EmailAgent(client=client)


@router.post("/analyze-email", response_model=AgentResult)
def analyze_email(payload: AnalyzeEmailRequest, agent: EmailAgent = Depends(get_email_agent)) -> AgentResult:
    message_id = (payload.message_id or "").strip() or f"test_{uuid4().hex}"
    internal = EmailInput(
        message_id=message_id,
        subject=payload.subject,
        sender=payload.from_email,
        recipients=[payload.to_email],
        body_text=payload.body,
        thread_context=payload.thread_context,
    )
    log.info("analyze_email request", extra={"message_id": internal.message_id})
    return agent.analyze_email(internal)

