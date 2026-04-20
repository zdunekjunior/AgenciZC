from __future__ import annotations

from app.agents.company.contracts import CaseAgentInput, CaseAgentOutput


class SecretaryAgent:
    """
    Role: secretary/ops
    - Organizes the case, ensures required info is present
    - Coordinates the workflow between agents
    - Produces draft actions/checklists for operator
    """

    name = "SecretaryAgent"

    def run(self, input: CaseAgentInput) -> CaseAgentOutput:
        email = input.case.source_email
        return CaseAgentOutput(
            notes=[f"Case opened for email subject={email.subject!r}"],
            decisions=["route_initial: orchestrator_decides_next_agents"],
            artifacts={"checklist": ["confirm sender", "check thread context", "verify intent", "prepare draft"]},
        )

