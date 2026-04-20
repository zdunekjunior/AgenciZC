from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.team.contracts import AgentError, AgentRun, AgentStatus
from app.cases.models import CaseContext
from app.schemas.sales import LeadStage, SalesDecision, SalesReview


@dataclass(frozen=True)
class SalesAgentInput:
    case: CaseContext


class SalesAgent:
    """
    Role: sales
    - Operacyjna ocena spraw sprzedażowych na bazie CaseContext
    - Ustala lead_stage, next action, follow-up plan i notatki
    - Przygotowuje dane pod przyszły CRM handoff (bez integracji)
    """

    name = "SalesAgent"

    def run(self, input: SalesAgentInput) -> AgentRun[SalesReview]:
        case = input.case
        email_text = ((case.subject or "") + "\n" + (case.from_email or "") + "\n").lower()

        if case.lead_scoring is None:
            return AgentRun(
                agent_name=self.name,
                status=AgentStatus.skipped,
                output=SalesReview(
                    sales_decision=SalesDecision.needs_info,
                    lead_stage=LeadStage.new,
                    recommended_next_action="Zbierz brakujące informacje (brak lead scoring).",
                    follow_up_plan=["Poproś o brief, zakres, budżet i termin."],
                    sales_notes="Brak lead scoring w CaseContext — SalesAgent wymaga wstępnego score/intent.",
                    confidence=0.35,
                ),
                errors=[
                    AgentError(
                        code="missing_lead_scoring",
                        message="CaseContext.lead_scoring is missing.",
                    )
                ],
            )

        s = case.lead_scoring
        score = int(s.lead_score)
        intent = s.business_intent.value
        temp = s.lead_temperature.value
        priority = s.sales_priority.value

        wants_call = any(k in (case.research_summary or "").lower() for k in ["call", "spotkanie", "demo"]) or any(
            k in email_text for k in ["call", "demo", "spotkanie", "rozmow"]
        )
        budget_hint = bool(re.search(r"\b(budżet|budzet|widełki|widelki|budget|pricing|cena|koszt)\b", (case.subject or "").lower()))

        # Decision heuristics
        if score >= 70:
            decision = SalesDecision.qualified
            stage = LeadStage.qualified
            next_action = "Zaproponuj krótki call (15–30 min) i zbierz wymagania (brief/zakres/budżet)."
            plan = [
                "Odpowiedz w ciągu 2h (w godzinach pracy).",
                "Zaproponuj 2–3 terminy call w tym tygodniu.",
                "Poproś o krótki brief + cele + deadline + budżet.",
            ]
            conf = 0.82
        elif score >= 40:
            decision = SalesDecision.follow_up
            stage = LeadStage.nurture if intent in ["other", "support", "recruitment"] else LeadStage.new
            next_action = "Dopytaj o zakres i budżet; jeśli potwierdzą, przejdź do kwalifikacji i call."
            plan = [
                "Wyślij ustrukturyzowane pytania kwalifikujące.",
                "Jeśli brak odpowiedzi: follow-up po 2 dniach roboczych.",
                "Jeśli dalej brak: follow-up po 7 dniach i zamknij jako stale.",
            ]
            conf = 0.68
        else:
            decision = SalesDecision.needs_info
            stage = LeadStage.new
            next_action = "Zbierz minimalny komplet danych; jeśli brak sygnałów biznesowych, traktuj jako low priority."
            plan = ["Poproś o cel, zakres, budżet, decydenta i deadline.", "Jeśli brak odpowiedzi: follow-up po 7 dniach."]
            conf = 0.52

        if wants_call and stage in (LeadStage.new, LeadStage.qualified):
            stage = LeadStage.meeting_proposed

        if intent in ["support", "recruitment"]:
            decision = SalesDecision.disqualified
            stage = LeadStage.lost
            next_action = "To nie jest lead sprzedażowy — przekieruj do właściwego procesu (support/HR)."
            plan = []
            conf = 0.85

        notes = (
            f"score={score} temp={temp} intent={intent} priority={priority}. "
            f"research={'yes' if bool(case.research_summary) else 'no'}. "
            f"drafts={len(case.draft_ids)}. "
            f"budget_signal={'yes' if budget_hint else 'no'}."
        )

        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.ok,
            output=SalesReview(
                sales_decision=decision,
                lead_stage=stage,
                recommended_next_action=next_action,
                follow_up_plan=plan,
                sales_notes=notes,
                confidence=conf,
            ),
            metadata={"score": score, "intent": intent, "priority": priority},
        )

