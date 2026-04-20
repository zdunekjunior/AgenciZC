from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.team.contracts import AgentRun, AgentStatus
from app.cases.models import CaseContext
from app.schemas.professor import ProfessorReview


@dataclass(frozen=True)
class ProfessorAgentInput:
    case: CaseContext


class ProfessorAgent:
    """
    Role: professor/research
    - Expert interpretation of the case (context + risks + key questions)
    - Produces practical notes for Secretary/Sales/Dev/Finance agents
    """

    name = "ProfessorAgent"

    def run(self, input: ProfessorAgentInput) -> AgentRun[ProfessorReview]:
        c = input.case
        subj = (c.subject or "").strip()
        body = ""
        # We only store minimal in CaseContext; use what we have.
        # For deeper analysis, use CaseContext.notes in future.
        if c.notes:
            body = "\n".join([n.text for n in c.notes[-5:]])
        text = (subj + "\n" + (c.research_summary or "") + "\n" + (c.lead_summary or "") + "\n" + (c.sales_notes or "") + "\n" + body).lower()

        domain_context = "Kontekst ogólny: sprawa biznesowa wymagająca doprecyzowania celu, zakresu i kryteriów sukcesu."
        if any(k in text for k in ["wdroż", "wdroze", "implement", "integrac", "api", "system", "produkcyj"]):
            domain_context = (
                "Kontekst wdrożeniowy: warto rozdzielić potrzeby biznesowe od wymagań technicznych "
                "(integracje, bezpieczeństwo, SLA, migracje, utrzymanie)."
            )
        if any(k in text for k in ["partner", "współpraca", "wspolpraca", "collaboration", "partnership"]):
            domain_context = (
                "Kontekst partnerski: kluczowe są cele współpracy, wartość dla obu stron, role/odpowiedzialności, "
                "warunki komercyjne i ryzyka reputacyjne."
            )

        key_risks: list[str] = []
        if any(k in text for k in ["termin", "deadline", "asap", "pilne"]):
            key_risks.append("Ryzyko nierealnych terminów bez pełnych wymagań (scope creep).")
        if any(k in text for k in ["budżet", "budzet", "pricing", "cena", "koszt"]):
            key_risks.append("Ryzyko nieporozumień budżetowych (brak modelu rozliczeń i zakresu).")
        if any(k in text for k in ["dane", "rodo", "gdpr", "security", "bezpieczeń"]):
            key_risks.append("Ryzyko compliance/bezpieczeństwa: wymagane doprecyzowanie przetwarzania danych i uprawnień.")
        if not key_risks:
            key_risks = ["Brak pełnego kontekstu — ryzyko błędnych założeń i nieprecyzyjnej odpowiedzi."]

        key_questions = [
            "Jaki jest cel biznesowy i oczekiwany rezultat (1–2 zdania)?",
            "Jaki jest zakres (deliverables) i odpowiedzialność stron?",
            "Jaki jest deadline / priorytety czasowe i co jest 'must have' w MVP?",
            "Czy są preferencje dot. budżetu / modelu rozliczeń?",
            "Kto jest decydentem i czy możemy zaproponować krótki call?",
        ]
        if re.search(r"\b(api|integrac|system)\b", text):
            key_questions.append("Jakie systemy/integracje wchodzą w grę (API, auth, dane, środowiska)?")

        problem_interpretation = (
            "Najpewniej jest to zapytanie biznesowe, w którym potrzebujemy zebrać brakujące informacje, "
            "żeby zaproponować bezpieczne kolejne kroki."
        )
        if c.research_summary:
            problem_interpretation = f"{c.research_summary} (interpretacja ekspercka: doprecyzuj kluczowe parametry)."

        expert_summary = (
            "Rekomendacja ekspercka: potraktuj sprawę jako kwalifikację + doprecyzowanie. "
            "Nie składaj obietnic terminów/cen bez briefu i zakresu. Zaproponuj call i listę pytań."
        )
        recommended_next_step = "Wyślij krótką odpowiedź: potwierdź, zadaj 5–7 pytań, zaproponuj call 15–30 min."

        confidence = 0.72 if (c.research_summary or c.lead_scoring) else 0.55

        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.ok,
            output=ProfessorReview(
                expert_summary=expert_summary,
                problem_interpretation=problem_interpretation,
                domain_context=domain_context,
                key_risks=key_risks,
                key_questions=key_questions,
                recommended_expert_next_step=recommended_next_step,
                confidence=confidence,
            ),
            metadata={"has_research": bool(c.research_summary), "has_sales_notes": bool(c.sales_notes)},
        )

