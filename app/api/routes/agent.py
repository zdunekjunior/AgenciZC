from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.agents.email_agent import EmailAgent
from app.agents.team.draft_agent import DraftAgent
from app.agents.team.inbox_agent import InboxAgent
from app.agents.team.lead_scoring_agent import LeadScoringAgent
from app.agents.team.research_agent import ResearchAgent
from app.agents.company.sales_agent import SalesAgent
from app.agents.company.professor_agent import ProfessorAgent
from app.api.routes.audit import get_audit_service
from app.api.routes.cases import get_case_service
from app.api.routes.leads import get_lead_service
from app.audit.service import AuditLogService
from app.cases.service import CaseService
from app.config import Settings, get_settings
from app.leads.service import LeadService
from app.orchestrator.email_orchestrator import EmailOrchestrator
from app.schemas.email import AgentResult, AnalyzeEmailRequest, EmailInput
from app.services.openai_client import OpenAIResponsesClient

router = APIRouter()
log = logging.getLogger(__name__)


def get_openai_client(settings: Settings = Depends(get_settings)) -> OpenAIResponsesClient:
    return OpenAIResponsesClient.from_settings(settings)


def get_email_agent(client: OpenAIResponsesClient = Depends(get_openai_client)) -> EmailAgent:
    return EmailAgent(client=client)


def get_orchestrator(
    email_agent: EmailAgent = Depends(get_email_agent),
    audit: AuditLogService = Depends(get_audit_service),
    leads: LeadService = Depends(get_lead_service),
    cases: CaseService = Depends(get_case_service),
) -> EmailOrchestrator:
    inbox_agent = InboxAgent(email_agent=email_agent)
    draft_agent = DraftAgent()
    research_agent = ResearchAgent()
    lead_agent = LeadScoringAgent()
    sales_agent = SalesAgent()
    prof_agent = ProfessorAgent()
    return EmailOrchestrator(
        inbox_agent=inbox_agent,
        draft_agent=draft_agent,
        research_agent=research_agent,
        lead_scoring_agent=lead_agent,
        sales_agent=sales_agent,
        professor_agent=prof_agent,
        leads=leads,
        cases=cases,
        audit=audit,
    )


@router.post("/analyze-email", response_model=AgentResult)
def analyze_email(
    payload: AnalyzeEmailRequest,
    orch: EmailOrchestrator = Depends(get_orchestrator),
    cases: CaseService = Depends(get_case_service),
) -> AgentResult:
    message_id = (payload.message_id or "").strip() or f"test_{uuid4().hex}"
    internal = EmailInput(
        message_id=message_id,
        subject=payload.subject,
        sender=payload.from_email,
        recipients=[payload.to_email],
        body_text=payload.body,
        thread_context=payload.thread_context,
    )
    cases.get_or_create_from_email(email=internal, source_type="api")
    log.info("analyze_email request", extra={"message_id": internal.message_id})
    return orch.handle_email(internal)

