from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.team.contracts import AgentError, AgentRun, AgentStatus
from app.schemas.email import EmailInput


@dataclass(frozen=True)
class ResearchAgentInput:
    email: EmailInput
    query: str


@dataclass(frozen=True)
class ResearchAgentOutput:
    summary: str
    sources: list[str] = field(default_factory=list)


class ResearchAgent:
    """
    Stub/placeholder agent for future web research tool calling.
    """

    name = "ResearchAgent"

    def run(self, input: ResearchAgentInput) -> AgentRun[ResearchAgentOutput]:
        # No real research yet; return a stub result that is safe and auditable.
        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.skipped,
            output=ResearchAgentOutput(
                summary="Research stub: web research is not implemented yet. Escalate for human verification if needed.",
                sources=[],
            ),
            metadata={"query": input.query},
            errors=[
                AgentError(
                    code="not_implemented",
                    message="ResearchAgent is a stub (no external web search executed).",
                )
            ],
        )

