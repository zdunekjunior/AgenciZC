from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.team.contracts import AgentRun, AgentStatus
from app.agents.team.research_agent import ResearchAgentOutput
from app.domain.leads import BusinessIntent, LeadTemperature, SalesPriority
from app.schemas.email import AgentResult, EmailInput
from app.schemas.leads import LeadScoring


@dataclass(frozen=True)
class LeadScoringAgentInput:
    email: EmailInput
    analysis: AgentResult
    research: ResearchAgentOutput | None = None


class LeadScoringAgent:
    """
    Heuristic lead scoring (no external CRM/search).

    Produces a practical 0-100 score + intent + priority + followup guidance.
    """

    name = "LeadScoringAgent"

    def run(self, input: LeadScoringAgentInput) -> AgentRun[LeadScoring]:
        email = input.email
        text = ((email.subject or "") + "\n" + (email.body_text or "")).lower()

        intent = _detect_intent(text)
        score = 10

        # Strong intent
        if intent in (BusinessIntent.offer, BusinessIntent.partnership, BusinessIntent.implementation):
            score += 25

        # Urgency / meeting
        if any(k in text for k in ["pilne", "asap", "na jutro", "termin", "deadline", "spotkanie", "call", "demo"]):
            score += 10

        # Budget signals
        if re.search(r"\b(budżet|budzet|widełki|widelki|budget|cena|pricing|koszt)\b", text):
            score += 15

        # Company / decision maker signals
        if any(k in text for k in ["spółka", "spolka", "firma", "company", "zarząd", "zarzad", "ceo", "cto", "head of"]):
            score += 10

        # Research adds clarity
        if input.research is not None:
            score += 5

        # Penalize support/recruitment
        if intent in (BusinessIntent.support, BusinessIntent.recruitment):
            score = max(0, score - 20)

        score = max(0, min(100, score))
        temperature = _temperature(score)
        priority = _priority(score, intent)

        followup = _followup(intent=intent, temperature=temperature)
        notes = _notes(intent=intent, text=text, research=input.research)

        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.ok,
            output=LeadScoring(
                lead_score=score,
                lead_temperature=temperature,
                business_intent=intent,
                sales_priority=priority,
                recommended_followup=followup,
                qualification_notes=notes,
            ),
        )


def _detect_intent(text: str) -> BusinessIntent:
    if any(k in text for k in ["wdroż", "wdroze", "implement", "integracja", "deployment", "migracja"]):
        return BusinessIntent.implementation
    if any(k in text for k in ["partner", "partnerstwo", "współpraca", "wspolpraca", "collaboration", "partnership"]):
        return BusinessIntent.partnership
    if any(k in text for k in ["oferta", "proposal", "propozycja", "deal", "pricing"]):
        return BusinessIntent.offer
    if any(k in text for k in ["problem", "błąd", "blad", "support", "pomoc", "nie działa", "nie dziala"]):
        return BusinessIntent.support
    if any(k in text for k in ["rekrut", "cv", "resume", "stanowisko", "aplikuj", "recruitment"]):
        return BusinessIntent.recruitment
    return BusinessIntent.other


def _temperature(score: int) -> LeadTemperature:
    if score >= 70:
        return LeadTemperature.hot
    if score >= 40:
        return LeadTemperature.warm
    return LeadTemperature.cold


def _priority(score: int, intent: BusinessIntent) -> SalesPriority:
    if intent in (BusinessIntent.offer, BusinessIntent.partnership, BusinessIntent.implementation) and score >= 70:
        return SalesPriority.high
    if score >= 40:
        return SalesPriority.medium
    return SalesPriority.low


def _followup(*, intent: BusinessIntent, temperature: LeadTemperature) -> str:
    if intent == BusinessIntent.partnership:
        return "Poproś o krótki brief i zaproponuj call 15–30 min."
    if intent == BusinessIntent.implementation:
        return "Zbierz wymagania (zakres, terminy, budżet) i zaproponuj spotkanie discovery."
    if intent == BusinessIntent.offer:
        return "Potwierdź zainteresowanie, poproś o kontekst i zaproponuj kolejny krok (call/demo)."
    if temperature == LeadTemperature.hot:
        return "Szybki follow-up dziś: doprecyzuj warunki i umów rozmowę."
    return "Odpowiedz z pytaniami kwalifikującymi i zaproponuj kolejny krok."


def _notes(*, intent: BusinessIntent, text: str, research: ResearchAgentOutput | None) -> str:
    parts: list[str] = [f"intent={intent.value}"]
    if research is not None:
        parts.append("research_used=true")
        if research.missing_information:
            parts.append(f"missing_info_count={len(research.missing_information)}")
    if "budżet" in text or "budget" in text:
        parts.append("budget_signal=true")
    return " | ".join(parts)

