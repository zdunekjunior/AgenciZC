from __future__ import annotations

from app.agents.company.contracts import CaseAgentInput, CaseAgentOutput


class DevelopmentAgent:
    """
    Role: development
    - Feasibility checks, scope framing, roadmap suggestions
    - Extracts requirements and risks from the case
    """

    name = "DevelopmentAgent"

    def run(self, input: CaseAgentInput) -> CaseAgentOutput:
        email = input.case.source_email
        return CaseAgentOutput(
            notes=["Extract requirements, constraints, and propose an implementation plan."],
            decisions=["dev:needs_requirements"],
            artifacts={
                "requirements_questions": [
                    "Jaki jest zakres (MVP vs pełny)?",
                    "Jakie integracje/systemy wchodzą w grę?",
                    "Jakie są kryteria sukcesu i terminy?",
                ],
                "context": {"subject": email.subject},
            },
        )

