from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.email_agent import EmailAgent
from app.agents.company.sales_agent import SalesAgent, SalesAgentInput
from app.agents.team.draft_agent import DraftAgent
from app.agents.team.inbox_agent import InboxAgent
from app.agents.team.lead_scoring_agent import LeadScoringAgent
from app.agents.team.research_agent import ResearchAgent
from app.api.routes.audit import get_audit_service
from app.api.routes.cases import get_case_service
from app.api.routes.leads import get_lead_service
from app.audit.service import AuditLogService
from app.auth.admin_auth import require_admin_session
from app.cases.service import CaseService
from app.config import Settings, get_settings
from app.leads.service import LeadService
from app.orchestrator.email_orchestrator import EmailOrchestrator
from app.schemas.email import EmailInput
from app.schemas.sales import SalesReview
from app.services.openai_client import OpenAIResponsesClient


router = APIRouter(dependencies=[Depends(require_admin_session)])


@lru_cache(maxsize=1)
def get_sales_agent() -> SalesAgent:
    return SalesAgent()


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
    return EmailOrchestrator(
        inbox_agent=inbox_agent,
        draft_agent=draft_agent,
        research_agent=research_agent,
        lead_scoring_agent=lead_agent,
        sales_agent=sales_agent,
        leads=leads,
        cases=cases,
        audit=audit,
    )


class SalesReviewRequest(BaseModel):
    case_id: str | None = None

    # Optional: allow creating a case from an email payload (same as /agent/analyze-email)
    message_id: str | None = None
    subject: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    body: str | None = None
    thread_context: list[str] = Field(default_factory=list)


class SalesReviewResponse(BaseModel):
    case_id: str
    sales_review: SalesReview


def _email_from_request(req: SalesReviewRequest) -> EmailInput:
    mid = (req.message_id or "").strip() or f"test_{uuid4().hex}"
    return EmailInput(
        message_id=mid,
        subject=req.subject,
        sender=req.from_email,
        recipients=[req.to_email] if req.to_email else [],
        body_text=req.body or "",
        thread_context=req.thread_context,
    )


@router.post("/review", response_model=SalesReviewResponse)
def review_sales_case(
    payload: SalesReviewRequest,
    cases: CaseService = Depends(get_case_service),
    sales: SalesAgent = Depends(get_sales_agent),
    orch: EmailOrchestrator = Depends(get_orchestrator),
) -> SalesReviewResponse:
    case = None
    if payload.case_id:
        case = cases.get(case_id=payload.case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
    else:
        email = _email_from_request(payload)
        case = cases.get_or_create_from_email(email=email, source_type="api")
        # Enrich case with lead scoring / research by running existing orchestration flow.
        orch.handle_email(email)
        case = cases.get_by_message_id(message_id=email.message_id) or case

    run = sales.run(SalesAgentInput(case=case))
    if run.output is None:
        raise HTTPException(status_code=500, detail="SalesAgent returned no output")

    cases.apply_sales_review(case=case, review=run.output)
    return SalesReviewResponse(case_id=case.case_id, sales_review=run.output)

