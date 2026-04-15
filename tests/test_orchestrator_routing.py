from __future__ import annotations

from dataclasses import dataclass

from app.agents.team.contracts import AgentRun, AgentStatus
from app.domain.enums import Category, Priority, RecommendedAction, SuggestedTool
from app.orchestrator.email_orchestrator import EmailOrchestrator
from app.schemas.email import AgentResult, EmailInput


@dataclass
class SpyInboxAgent:
    name: str = "InboxAgent"
    calls: int = 0
    result: AgentResult | None = None

    def run(self, input):  # type: ignore[no-untyped-def]
        self.calls += 1
        assert self.result is not None
        return AgentRun(agent_name=self.name, status=AgentStatus.ok, output=self.result)


@dataclass
class SpyDraftAgent:
    name: str = "DraftAgent"
    calls: int = 0

    def run(self, input):  # type: ignore[no-untyped-def]
        self.calls += 1
        return AgentRun(agent_name=self.name, status=AgentStatus.ok, output=type("O", (), {"draft_reply": input.draft_reply})())


@dataclass
class SpyResearchAgent:
    name: str = "ResearchAgent"
    calls: int = 0

    def run(self, input):  # type: ignore[no-untyped-def]
        self.calls += 1
        return AgentRun(agent_name=self.name, status=AgentStatus.skipped, output=None)


def _email() -> EmailInput:
    return EmailInput(
        message_id="m1",
        thread_id="t1",
        subject="Test",
        sender="a@example.com",
        recipients=["b@example.com"],
        body_text="Hello",
        thread_context=[],
    )


def test_orchestrator_routes_to_inbox_agent() -> None:
    inbox = SpyInboxAgent(
        result=AgentResult(
            category=Category.other,
            priority=Priority.medium,
            summary="s",
            needs_human_approval=False,
            recommended_action=RecommendedAction.draft_for_review,
            draft_reply="hi",
            reasoning_notes="n",
            suggested_tool=SuggestedTool.none,
            confidence=0.9,
        )
    )
    draft = SpyDraftAgent()
    research = SpyResearchAgent()

    orch = EmailOrchestrator(inbox_agent=inbox, draft_agent=draft, research_agent=research)  # type: ignore[arg-type]
    orch.handle_email(_email())

    assert inbox.calls == 1


def test_orchestrator_routes_to_draft_agent_for_simple_email() -> None:
    inbox = SpyInboxAgent(
        result=AgentResult(
            category=Category.other,
            priority=Priority.medium,
            summary="s",
            needs_human_approval=False,
            recommended_action=RecommendedAction.draft_for_review,
            draft_reply="hi",
            reasoning_notes="n",
            suggested_tool=SuggestedTool.none,
            confidence=0.9,
        )
    )
    draft = SpyDraftAgent()
    research = SpyResearchAgent()

    orch = EmailOrchestrator(inbox_agent=inbox, draft_agent=draft, research_agent=research)  # type: ignore[arg-type]
    orch.handle_email(_email())

    assert draft.calls == 1
    assert research.calls == 0


def test_orchestrator_routes_to_research_agent_when_suggested() -> None:
    inbox = SpyInboxAgent(
        result=AgentResult(
            category=Category.other,
            priority=Priority.medium,
            summary="s",
            needs_human_approval=False,
            recommended_action=RecommendedAction.draft_for_review,
            draft_reply="hi",
            reasoning_notes="n",
            suggested_tool=SuggestedTool.web_research,
            confidence=0.9,
        )
    )
    draft = SpyDraftAgent()
    research = SpyResearchAgent()

    orch = EmailOrchestrator(inbox_agent=inbox, draft_agent=draft, research_agent=research)  # type: ignore[arg-type]
    out = orch.handle_email(_email())

    assert research.calls == 1
    assert out.needs_human_approval is True
