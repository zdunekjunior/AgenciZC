from __future__ import annotations

from dataclasses import dataclass

from app.agents.team.contracts import AgentRun, AgentStatus
from app.schemas.email import EmailInput


@dataclass(frozen=True)
class DraftAgentInput:
    email: EmailInput
    draft_reply: str


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
        return AgentRun(agent_name=self.name, status=AgentStatus.ok, output=DraftAgentOutput(draft_reply=draft))

