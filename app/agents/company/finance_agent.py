from __future__ import annotations

from app.agents.company.contracts import CaseAgentInput, CaseAgentOutput


class FinanceAgent:
    """
    Role: finance
    - Budgeting, pricing models, profitability checks
    - Produces finance notes and assumptions (no hard promises)
    """

    name = "FinanceAgent"

    def run(self, input: CaseAgentInput) -> CaseAgentOutput:
        return CaseAgentOutput(
            notes=["Estimate pricing model options; request missing budget info if needed."],
            decisions=["finance:needs_budget_range"],
            artifacts={"pricing_models": ["fixed_price", "time_and_materials", "retainer"]},
        )

