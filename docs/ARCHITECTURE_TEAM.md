# Inbox Assistant — docelowy zespół agentów (model “firma 5-osobowa”)

Ten dokument opisuje docelową architekturę “team-of-agents” dla projektu Inbox Assistant.
Na tym etapie w repo istnieją **kontrakty + szkielety + modele danych**, bez podpinania do produkcyjnego flow.

## Założenia
- System działa **draft-first**: bez automatycznego wysyłania maili.
- Orchestrator koordynuje pracę agentów i **eskaluje do człowieka** w sytuacjach ryzykownych.
- Agenci współdzielą jeden “plik sprawy” (`CaseContext`) i dopisują do niego artefakty, notatki i decyzje.

## 1) Agent role model (5 ról)

Wspólny kontrakt “case agentów” (foundation):
- **Input**: `CaseAgentInput(case: CaseContext)`
- **Output**: `CaseAgentOutput(notes, decisions, artifacts)`
- **Cel**: produkcja *konkretnego wkładu* do `CaseContext`, nie “finalnej odpowiedzi”.

### 1. SecretaryAgent (ops + koordynacja)
- **Odpowiedzialność**: otwiera sprawę, normalizuje dane, pilnuje kompletności, proponuje checklistę, koordynuje agentów.
- **Input**: `CaseContext` (email + aktualne artefakty)
- **Output**: checklisty, decyzje routingu, brakujące informacje
- **Kiedy wywoływany**: zawsze jako pierwszy krok
- **Decyzje**:
  - czy case ma komplet danych do kolejnych agentów
  - czy od razu trzeba eskalować do człowieka (np. compliance/safety)
- **Zapis do case**:
  - `notes`: “co wiemy / czego brakuje”
  - `decisions`: “routing”
  - `artifacts.checklist`

### 2. SalesAgent (sprzedaż + follow-up)
- **Odpowiedzialność**: kwalifikacja okazji, follow-up, pytania kwalifikujące, przygotowanie danych pod CRM.
- **Input**: `CaseContext` + (opcjonalnie) `lead_scoring`
- **Output**: priorytet sprzedażowy, następne kroki, pytania
- **Kiedy wywoływany**: gdy orchestrator wykryje intencję biznesową / lead
- **Decyzje**:
  - czy to realny lead czy “support/other”
  - follow-up: call/demo, pytania, propozycja następnego kroku
- **Zapis do case**:
  - `lead_scoring` (snapshot / wynik)
  - `notes` i `artifacts.recommended_followup`

### 3. DevelopmentAgent (zakres + wykonalność + roadmap)
- **Odpowiedzialność**: analiza wykonalności, zakres MVP vs full, ryzyka, roadmap.
- **Input**: `CaseContext` (problem/opis, oczekiwania)
- **Output**: wymagania, ryzyka, lista pytań doprecyzowujących, propozycja planu
- **Kiedy wywoływany**: gdy sprawa dotyczy wdrożenia/produktu/feature
- **Decyzje**:
  - czy trzeba dopytać o wymagania / integracje / SLA
  - klasyfikacja ryzyk (czas, budżet, bezpieczeństwo)
- **Zapis do case**:
  - `notes` (założenia + ryzyka)
  - `artifacts.requirements_questions`, `artifacts.roadmap_draft`

### 4. ProfessorAgent (research + synteza + ekspert)
- **Odpowiedzialność**: research, synteza, wyjaśnienia, analiza branżowa; dostarcza “kontekst do decyzji”.
- **Input**: `CaseContext`
- **Output**: streszczenie researchu, rekomendacje źródeł/hipotez, “co jest prawdą vs przypuszczeniem”
- **Kiedy wywoływany**: gdy sprawa jest niejasna, wymaga wytłumaczenia, lub jest ryzyko błędnych założeń
- **Decyzje**:
  - czy potrzebujemy dodatkowych źródeł
  - jakie są alternatywy/konsekwencje
- **Zapis do case**:
  - `notes` (research summary)
  - `artifacts.topics`, docelowo: `artifacts.sources`

### 5. FinanceAgent (wyceny + budżet + opłacalność)
- **Odpowiedzialność**: budżety, modele rozliczeń, zakres cen, opłacalność.
- **Input**: `CaseContext` (zakres + priorytet + ograniczenia)
- **Output**: propozycja modelu rozliczeń, pytania o budżet, wstępne widełki (z zastrzeżeniami)
- **Kiedy wywoływany**: gdy sprawa ma komponent wyceny/zakupu/ROI
- **Decyzje**:
  - fixed price vs T&M vs retainer
  - kiedy “brak danych → eskalacja / dopytanie”
- **Zapis do case**:
  - `notes` (założenia finansowe)
  - `artifacts.pricing_models`, docelowo: `artifacts.estimate`

## 2) Shared case context (Case file)
Model “case file” jest w `app/cases/models.py`:
- **source**: `source_email: EmailInput`
- **collab**:
  - `notes[]` (notatki agentów)
  - `decisions[]` (decyzje agentów/orchestratora/człowieka)
- **artifacts**:
  - `lead_scoring` (snapshot)
  - `draft_ids[]` (np. Gmail draft_id)
  - `audit_entity_ids[]` (np. message_id, draft_id, itp. pod `AuditLogService`)

Repozytorium foundation (in-memory) jest w `app/cases/repository.py` (`InMemoryCaseRepository`).

## 3) Orchestrator strategy (decyzje i kolejność pracy)
Foundation orchestratora “firmowego” jest w `app/orchestrator/company_orchestrator.py`.

### Strategia (proponowana)
- **Planowanie**: `plan(case) -> OrchestratorPlan(steps, stop_condition, escalate_condition)`
- **Kolejność default**:
  - Secretary → (Sales/Professor/Dev/Finance wg sygnałów) → finalizacja odpowiedzi
- **Dobór agentów (heurystycznie na start)**:
  - biznes/partnerstwo/oferta/implementacje → Sales + (Professor opcjonalnie) + Dev + Finance
  - sprawy niejasne / ryzykowne → Professor wcześniej
  - brak danych krytycznych → Secretary (dopytanie) + eskalacja

### Kiedy zakończyć sprawę
Case można zakończyć, gdy:
- jest gotowa **bezpieczna rekomendacja** (next steps + pytania doprecyzowujące), oraz
- powstał draft (jeśli ma sens), lub decyzja “skip/needs_human”.

### Kiedy eskalować do człowieka
Eskalacja jeśli:
- `needs_human_approval=True` (twarde reguły / ryzykowne kategorie),
- niska pewność / sprzeczne rekomendacje agentów,
- wątek dotyczy kwestii prawnych, bezpieczeństwa, finansowych obietnic.

## 4) Learning foundation (bez trenowania modelu)
Celem jest “uczenie się z feedbacku” przez **pamięć i playbooki**, nie przez training.

Modele foundation:
- `app/learning/models.py`:
  - `Playbook` — reusable instrukcje wyciągnięte z dobrych case’ów
  - `FeedbackMemoryItem` — pamięć: “co zapamiętać” + przykłady + verdict
  - `HumanCorrection` — poprawki człowieka (before/after)
  - `CaseOutcome` — outcome sprawy (np. won/lost/resolved)
- `app/learning/repository.py`: `InMemoryLearningRepository` (foundation)

### Co przechowywać
- **approved outputs**: zatwierdzone drafty, zaakceptowane lead scoring, decyzje
- **rejected outputs**: odrzucone drafty + powód
- **human corrections**: przed/po + notatka
- **reusable playbooks**: “gdy X → użyj struktury Y”
- **case outcomes**: win/loss/resolved + reason
- **feedback memory**: małe, wyszukiwalne “lesson learned”

## 5) Roadmap wdrożenia (high-level)
Patrz końcówka tego dokumentu + README (sekcja “Roadmap” w odpowiedzi od agenta).

## Mapa plików (to już jest w repo)
- `app/cases/models.py`, `app/cases/repository.py`
- `app/agents/company/*` (Secretary/Sales/Development/Professor/Finance)
- `app/orchestrator/company_orchestrator.py`
- `app/learning/models.py`, `app/learning/repository.py`

