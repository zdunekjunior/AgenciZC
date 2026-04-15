from __future__ import annotations

from dataclasses import dataclass

from app.agents.team.contracts import AgentError, AgentRun, AgentStatus
from app.domain.enums import Category
from app.schemas.email import EmailInput


@dataclass(frozen=True)
class ResearchAgentInput:
    email: EmailInput
    category: Category | None = None


@dataclass(frozen=True)
class ResearchAgentOutput:
    research_summary: str
    missing_information: list[str]
    recommended_questions: list[str]
    next_step_recommendation: str


class ResearchAgent:
    """
    Research agent (no web search yet).

    Produces helpful business-oriented analysis based on the email content,
    ready to be used by DraftAgent to create a better reply.
    """

    name = "ResearchAgent"

    def run(self, input: ResearchAgentInput) -> AgentRun[ResearchAgentOutput]:
        email = input.email
        text = ((email.subject or "") + "\n" + (email.body_text or "")).strip().lower()

        is_partnership = any(k in text for k in ["partner", "partnerstwo", "współpraca", "wspolpraca", "collaboration"])
        is_offer = any(k in text for k in ["oferta", "propozycja", "proposal", "deal", "wspólnie", "wspolnie"])

        missing: list[str] = [
            "Jaki jest cel współpracy/oferty i oczekiwany rezultat?",
            "Jaki jest zakres (co dokładnie mamy dostarczyć / jaki jest wkład stron)?",
            "Jaki jest timeline (start, deadline, kluczowe daty)?",
            "Jaki jest budżet / model rozliczeń (jeśli dotyczy)?",
            "Kto jest decydentem i kto będzie po stronie operacyjnej?",
        ]

        questions: list[str] = [
            "Czy możesz krótko opisać cel i kontekst tej propozycji?",
            "Jaki zakres współpracy rozważacie (deliverables / odpowiedzialności)?",
            "Jakie są oczekiwane terminy oraz kryteria sukcesu?",
            "Czy macie preferowany model rozliczeń lub widełki budżetowe (jeśli dotyczy)?",
            "Kto będzie najlepszą osobą do dalszych ustaleń i czy możemy zaproponować krótkie spotkanie?",
        ]

        if is_partnership:
            research_summary = (
                "Mail wygląda na zapytanie o partnerstwo/współpracę. "
                "Najważniejsze jest doprecyzowanie celu, zakresu, odpowiedzialności stron oraz warunków komercyjnych."
            )
            next_step = "Odpowiedz z krótkim potwierdzeniem i zestawem pytań doprecyzowujących; zaproponuj call 15–30 min."
        elif is_offer:
            research_summary = (
                "Mail wygląda na propozycję/ofertę. "
                "Warto szybko potwierdzić zainteresowanie i zebrać brakujące informacje (zakres, terminy, budżet, decydenci)."
            )
            next_step = "Odpowiedz z ustrukturyzowanymi pytaniami i prośbą o materiały/brief; zaproponuj termin rozmowy."
        else:
            research_summary = (
                "Mail może dotyczyć złożonego zapytania biznesowego. "
                "Doprecyzuj cel, wymagania i kryteria sukcesu zanim podasz konkret."
            )
            next_step = "Zbierz brakujące informacje pytaniami; dopiero potem przedstaw propozycję kolejnych kroków."

        return AgentRun(
            agent_name=self.name,
            status=AgentStatus.ok,
            output=ResearchAgentOutput(
                research_summary=research_summary,
                missing_information=missing,
                recommended_questions=questions,
                next_step_recommendation=next_step,
            ),
            metadata={"category_hint": str(input.category.value) if input.category else None},
            errors=[
                AgentError(
                    code="no_web_search",
                    message="ResearchAgent ran without external web search (heuristics only).",
                )
            ],
        )

