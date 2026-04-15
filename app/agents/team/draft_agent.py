from __future__ import annotations

from dataclasses import dataclass

from app.agents.team.contracts import AgentRun, AgentStatus
from app.agents.team.research_agent import ResearchAgentOutput
from app.schemas.email import EmailInput


@dataclass(frozen=True)
class DraftAgentInput:
    email: EmailInput
    draft_reply: str
    research: ResearchAgentOutput | None = None


@dataclass(frozen=True)
class DraftAgentOutput:
    draft_reply: str


class DraftAgent:
    """
    Draft agent: produces the final draft reply text.

    For now it simply validates/passes through the draft produced by InboxAgent.
    Later it can become its own model/tool-driven step.
    """

    name = "DraftAgent"

    def run(self, input: DraftAgentInput) -> AgentRun[DraftAgentOutput]:
        draft = (input.draft_reply or "").strip()
        if not draft:
            return AgentRun(
                agent_name=self.name,
                status=AgentStatus.skipped,
                output=DraftAgentOutput(draft_reply=""),
                metadata={"reason": "empty_draft"},
            )
        if input.research is None:
            return AgentRun(agent_name=self.name, status=AgentStatus.ok, output=DraftAgentOutput(draft_reply=draft))

        # Enrich draft with research-driven structure and clarifying questions.
        qs = [q.strip() for q in (input.research.recommended_questions or []) if q and q.strip()]
        qs = qs[:5]

        opening = "Dzień dobry,\n\nDziękuję za wiadomość. "
        context = f"{input.research.research_summary}\n"
        questions_block = ""
        if qs:
            questions_block = "Żeby przygotować konkretną propozycję, proszę o doprecyzowanie:\n" + "\n".join(
                [f"- {q}" for q in qs]
            )
            questions_block += "\n"
        next_step = f"\nProponowany kolejny krok: {input.research.next_step_recommendation}\n"
        closing = "\nPozdrawiam,\n"

        enriched = (opening + "\n" + context + "\n" + questions_block + next_step + closing).strip()
        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.ok,
            output=DraftAgentOutput(draft_reply=enriched),
            metadata={"enriched_with_research": True},
        )

