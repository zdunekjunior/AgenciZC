from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.agents.email_agent import EmailAgent
from app.agents.team.draft_agent import DraftAgent
from app.agents.team.inbox_agent import InboxAgent
from app.agents.team.lead_scoring_agent import LeadScoringAgent
from app.agents.team.research_agent import ResearchAgent
from app.agents.company.sales_agent import SalesAgent
from app.agents.company.professor_agent import ProfessorAgent
from app.config import Settings, get_settings
from app.api.routes.audit import get_audit_service
from app.api.routes.cases import get_case_service
from app.api.routes.drafts import get_draft_service
from app.api.routes.leads import get_lead_service
from app.audit.service import AuditLogService
from app.cases.service import CaseService
from app.domain.audit import ActorType, EntityType
from app.drafts.service import DraftApprovalService
from app.integrations.gmail.service import GmailApiError, GmailNotConfiguredError, GmailService
from app.domain.enums import RecommendedAction
from app.gatekeeper.inbox_gatekeeper import DECISION_REVIEW_ONLY
from app.orchestrator.email_orchestrator import EmailOrchestrator
from app.schemas.email import AgentResult
from app.schemas.gmail import (
    GmailAnalyzeAndDraftResult,
    GmailAnalyzeResult,
    GmailDraftResult,
    GmailMessageListItem,
    GmailMessageRequest,
    GmailMessagesListResponse,
)
from app.services.openai_client import OpenAIResponsesClient
from app.leads.service import LeadService

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


def get_gmail_service(settings: Settings = Depends(get_settings)) -> GmailService:
    try:
        return GmailService.from_settings(settings)
    except GmailNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Gmail integration not configured: {exc}",
        ) from exc


def _map_gmail_error(exc: GmailApiError) -> HTTPException:
    if exc.status_code == 404:
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=502, detail="Gmail API error (see server logs)")


def _headers_map(msg: dict) -> dict[str, str]:
    headers = msg.get("payload", {}).get("headers", []) or []
    out: dict[str, str] = {}
    for h in headers:
        name = (h.get("name") or "").strip().lower()
        value = (h.get("value") or "").strip()
        if name:
            out[name] = value
    return out


@router.post("/analyze-message", response_model=GmailAnalyzeResult)
def analyze_message(
    payload: GmailMessageRequest,
    gmail: GmailService = Depends(get_gmail_service),
    orch: EmailOrchestrator = Depends(get_orchestrator),
    cases: CaseService = Depends(get_case_service),
) -> GmailAnalyzeResult:
    try:
        msg = gmail.fetch_message(message_id=payload.message_id)
        email_input = gmail.fetch_email_input(message_id=payload.message_id)
    except GmailApiError as exc:
        raise _map_gmail_error(exc) from exc
    cases.get_or_create_from_email(email=email_input, source_type="gmail")
    result: AgentResult = orch.handle_email(email_input)

    return GmailAnalyzeResult(
        analysis=result.model_dump(),
        gmail_message_id=payload.message_id,
        gmail_thread_id=msg.get("threadId"),
    )


@router.post("/analyze-and-create-draft", response_model=GmailAnalyzeAndDraftResult)
def analyze_and_create_draft(
    payload: GmailMessageRequest,
    gmail: GmailService = Depends(get_gmail_service),
    orch: EmailOrchestrator = Depends(get_orchestrator),
    drafts: DraftApprovalService = Depends(get_draft_service),
    audit: AuditLogService = Depends(get_audit_service),
    leads: LeadService = Depends(get_lead_service),
    cases: CaseService = Depends(get_case_service),
) -> GmailAnalyzeAndDraftResult:
    try:
        msg = gmail.fetch_message(message_id=payload.message_id)
        email_input = gmail.fetch_email_input(message_id=payload.message_id)
    except GmailApiError as exc:
        raise _map_gmail_error(exc) from exc
    case = cases.get_or_create_from_email(email=email_input, source_type="gmail")
    result: AgentResult = orch.handle_email(email_input)

    draft_status = GmailDraftResult(status="skipped", draft_id=None, error=None, reason=None)
    action_taken = "skipped"
    label_names = ["AI/Analyzed", "AI/Skipped"]

    audit.log(
        entity_type=EntityType.email,
        entity_id=payload.message_id,
        action="email_analyzed",
        actor_type=ActorType.system,
        actor_name="gmail.analyze_and_create_draft",
        status="ok",
        metadata={"thread_id": msg.get("threadId")},
    )

    # Gatekeeper policy: create drafts only for reply_needed.
    if result.recommended_action != RecommendedAction.draft_for_review or not (result.draft_reply and result.draft_reply.strip()):
        draft_status = GmailDraftResult(status="skipped", draft_id=None, error=None, reason="auto_system_message")
        if result.recommended_action == RecommendedAction.ask_human:
            label_names = ["AI/Analyzed", "AI/ReviewOnly"]
    else:
        try:
            draft_id = gmail.create_reply_draft(original_message=msg, draft_reply=result.draft_reply)
            draft_status = GmailDraftResult(status="created", draft_id=draft_id, error=None, reason=None)
            action_taken = "draft_created"
            label_names = ["AI/Analyzed", "AI/DraftCreated"]
            audit.log(
                entity_type=EntityType.draft,
                entity_id=draft_id,
                action="draft_created",
                actor_type=ActorType.system,
                actor_name="GmailService",
                status="ok",
                metadata={"message_id": payload.message_id, "thread_id": msg.get("threadId")},
            )
            # Register for human approval (pending_review).
            lead = leads.get(entity_id=payload.message_id)
            drafts.register_new_draft(
                draft_id=draft_id,
                provider="gmail",
                message_id=payload.message_id,
                thread_id=msg.get("threadId"),
                draft_body=result.draft_reply,
                lead_scoring=lead.scoring if lead else None,
            )
            audit.log(
                entity_type=EntityType.draft,
                entity_id=draft_id,
                action="draft_moved_to_pending_review",
                actor_type=ActorType.system,
                actor_name="DraftApprovalService",
                status="ok",
                metadata={},
            )
            case = cases.link_draft_id(case=case, draft_id=draft_id)
            case = cases.touch_status(case=case, status="draft_linked")
        except HTTPException as exc:
            draft_status = GmailDraftResult(status="error", draft_id=None, error=str(exc.detail), reason=None)
        except Exception as exc:  # noqa: BLE001
            log.exception("Draft creation failed")
            draft_status = GmailDraftResult(status="error", draft_id=None, error=str(exc), reason=None)

    label_applied: list[str] = []
    try:
        label_applied = gmail.apply_labels(message_id=payload.message_id, label_names=label_names)
    except Exception:  # noqa: BLE001
        # Labeling should not break main flow; log and continue.
        log.exception("Failed to apply Gmail labels")

    return GmailAnalyzeAndDraftResult(
        analysis=result.model_dump(),
        gmail_message_id=payload.message_id,
        gmail_thread_id=msg.get("threadId"),
        draft=draft_status,
        label_applied=label_applied,
        action_taken=action_taken,
    )


@router.get("/messages", response_model=GmailMessagesListResponse)
def list_messages(
    limit: int = 10,
    gmail: GmailService = Depends(get_gmail_service),
) -> GmailMessagesListResponse:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")

    try:
        metas = gmail.list_recent_messages(limit=limit)
    except GmailApiError as exc:
        raise _map_gmail_error(exc) from exc

    items: list[GmailMessageListItem] = []
    for m in metas:
        headers = _headers_map(m)
        internal_ms = m.get("internalDate")
        internal_dt: datetime | None = None
        try:
            if internal_ms is not None:
                internal_dt = datetime.fromtimestamp(int(internal_ms) / 1000, tz=timezone.utc)
        except Exception:
            internal_dt = None

        items.append(
            GmailMessageListItem(
                message_id=m.get("id", ""),
                thread_id=m.get("threadId"),
                subject=headers.get("subject"),
                from_email=headers.get("from"),
                snippet=m.get("snippet"),
                internal_date=internal_dt,
            )
        )

    items = [x for x in items if x.message_id]
    return GmailMessagesListResponse(messages=items)


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str, gmail: GmailService = Depends(get_gmail_service)) -> dict:
    """
    Developer endpoint: return raw thread payload for debugging.
    """

    try:
        thread = gmail.fetch_thread(thread_id=thread_id)
    except GmailApiError as exc:
        raise _map_gmail_error(exc) from exc
    return thread

