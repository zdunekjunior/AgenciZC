from __future__ import annotations

from dataclasses import dataclass

from app.agents.company.contracts import CaseAgent, CaseAgentInput, CaseAgentOutput
from app.agents.company.roles import CompanyRole
from app.cases.models import CaseContext


@dataclass(frozen=True)
class OrchestratorPlanStep:
    role: CompanyRole
    reason: str


@dataclass(frozen=True)
class OrchestratorPlan:
    steps: list[OrchestratorPlanStep]
    stop_condition: str
    escalate_condition: str


class CompanyOrchestrator:
    """
    High-level orchestrator for the "5-person company" model.

    Not wired into production flow yet; foundation only.
    """

    def __init__(self, *, agents: dict[CompanyRole, CaseAgent]) -> None:
        self._agents = agents

    def plan(self, *, case: CaseContext) -> OrchestratorPlan:
        subj = (case.source_email.subject or "").lower()
        steps: list[OrchestratorPlanStep] = [OrchestratorPlanStep(role=CompanyRole.secretary, reason="Open and normalize case")]

        if any(k in subj for k in ["partner", "oferta", "współpraca", "wspolpraca", "wdroż", "wdroze", "implement"]):
            steps.append(OrchestratorPlanStep(role=CompanyRole.sales, reason="Qualify opportunity and follow-up"))
            steps.append(OrchestratorPlanStep(role=CompanyRole.professor, reason="Synthesize context/research (optional)"))
            steps.append(OrchestratorPlanStep(role=CompanyRole.development, reason="Feasibility and scope framing"))
            steps.append(OrchestratorPlanStep(role=CompanyRole.finance, reason="Pricing model / budget framing"))
        else:
            # Minimal path
            steps.append(OrchestratorPlanStep(role=CompanyRole.professor, reason="Clarify ambiguity if needed"))

        return OrchestratorPlan(
            steps=steps,
            stop_condition="Enough info to produce a safe draft + next steps",
            escalate_condition="Missing critical info / low confidence / high risk -> human approval required",
        )

    def run(self, *, case: CaseContext) -> list[CaseAgentOutput]:
        plan = self.plan(case=case)
        outputs: list[CaseAgentOutput] = []
        for step in plan.steps:
            agent = self._agents.get(step.role)
            if agent is None:
                continue
            outputs.append(agent.run(CaseAgentInput(case=case)))
        return outputs

