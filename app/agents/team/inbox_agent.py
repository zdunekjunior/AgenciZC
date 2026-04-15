from __future__ import annotations

from dataclasses import dataclass

from app.agents.email_agent import EmailAgent
from app.agents.team.contracts import AgentRun, AgentStatus
from app.schemas.email import AgentResult, EmailInput


@dataclass(frozen=True)
class InboxAgentInput:
    email: EmailInput


class InboxAgent:
    """
    Inbox agent: classification + safe draft suggestion (current model behavior).

    For now it reuses the existing EmailAgent and returns the full AgentResult.
    """

    name = "InboxAgent"

    def __init__(self, *, email_agent: EmailAgent) -> None:
        self._email_agent = email_agent

    def run(self, input: InboxAgentInput) -> AgentRun[AgentResult]:
        result = self._email_agent.analyze_email(input.email)
        return AgentRun(agent_name=self.name, status=AgentStatus.ok, output=result)

