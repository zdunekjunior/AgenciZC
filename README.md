# Inbox Assistant (AI agent backend)

Backendowy agent AI typu “Inbox Assistant” (draft-first). Na tym etapie działa na sztucznym wejściu JSON i **nigdy nie wysyła maili** — zwraca klasyfikację, streszczenie, rekomendowaną akcję i draft odpowiedzi.

## Wymagania
- Python 3.11+

## Jak sklonować i uruchomić lokalnie
1. Sklonuj repo:

```bash
git clone <URL_DO_REPO>
cd Agent_1LLM
```

2. Utwórz i uzupełnij `.env`:

```bash
cp .env.example .env
```

3. Zainstaluj zależności i uruchom:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Szybki start
1. Zainstaluj zależności:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Skonfiguruj środowisko:

```bash
cp .env.example .env
```

3. Uruchom API:

```bash
uvicorn app.main:app --reload
```

API będzie dostępne pod `http://127.0.0.1:8000`, a Swagger pod `http://127.0.0.1:8000/docs`.

## OpenAI: jak włączyć prawdziwy model
1. Skopiuj `.env.example` do `.env`:

```bash
cp .env.example .env
```

2. Ustaw klucz i (opcjonalnie) model:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
```

3. Uruchom aplikację i sprawdź logi:
- Gdy działa prawdziwe OpenAI zobaczysz log w stylu: `OpenAI MODE enabled. model=...`
- Gdy fallback/mock: `OpenAI MODE disabled -> MOCK MODE ...` albo `falling back to MOCK stub`

## Endpointy
- `GET /health` — health check
- `POST /agent/analyze-email` — analiza maila i draft odpowiedzi

## Tryb MOCK (fallback)
Jeśli `OPENAI_API_KEY` jest puste, serwis automatycznie przełącza się w tryb mock i zwraca deterministyczny wynik.

## Testy

```bash
pytest -q
```

## Miejsca na przyszłe integracje (placeholder)
- `app/integrations/gmail/` — przyszły Gmail API (na razie puste)
- `app/repositories/` — przyszłe repozytoria/baza danych (na razie puste)

## Gmail API (draft-first) — integracja lokalna
W projekcie są endpointy:
- `POST /gmail/analyze-message` — pobiera wiadomość z Gmail po `message_id`, mapuje do `EmailInput`, analizuje agentem i zwraca wynik
- `POST /gmail/analyze-and-create-draft` — jak wyżej, ale dodatkowo tworzy **draft** odpowiedzi w Gmail (bez wysyłki)
- `GET /gmail/messages` — lista ostatnich wiadomości (dev helper do znalezienia prawdziwego `message_id`)
- `GET /gmail/threads/{thread_id}` — (opcjonalnie) podgląd surowego payloadu wątku do debugowania

### Ochrona przed draftami do wiadomości automatycznych
System ma twarde reguły, które **blokują tworzenie draftów** dla wiadomości typu no-reply, alertów bezpieczeństwa i innych automatycznych powiadomień systemowych. W takim przypadku endpoint zwróci `draft.status="skipped"` z `draft.reason`.

### Flow (high-level)
- **analyze**: pobierz wiadomość + kontekst wątku → `EmailInput` → agent
- **decide**: agent + twarde reguły backendowe → `recommended_action`
- **create draft or skip**: utwórz draft tylko jeśli to bezpieczne i ma sens
- **apply label**: oznacz wiadomość w Gmail jako `AI/Analyzed` + (`AI/DraftCreated` lub `AI/Skipped`)

### Konfiguracja (refresh token)
To jest wersja dev oparta o refresh token. Musisz ręcznie skonfigurować projekt w Google Cloud.

1. W Google Cloud Console:
- utwórz projekt
- włącz **Gmail API**
- skonfiguruj **OAuth consent screen**
- utwórz **OAuth Client ID** (typ: Web application)
- dodaj redirect URI zgodny z `GOOGLE_REDIRECT_URI` (dla dev może być np. `http://localhost:8000/oauth/callback`)

2. Uzyskaj refresh token (jednorazowo):
- uruchom standardowy OAuth flow (np. własnym skryptem/Playground)
- zakresy: `https://www.googleapis.com/auth/gmail.modify`
- zapisz `refresh_token`

3. Uzupełnij `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/callback
GOOGLE_REFRESH_TOKEN=...
GMAIL_USER_EMAIL=me
```

### Testowanie endpointów
Najpierw pobierz prawdziwe ID wiadomości:

```bash
curl -s "http://127.0.0.1:8000/gmail/messages?limit=10"
```

Skopiuj `message_id` z odpowiedzi i użyj go w analizie:

Przykład:

```bash
curl -s http://127.0.0.1:8000/gmail/analyze-message \
  -H "Content-Type: application/json" \
  -d '{"message_id":"<GMAIL_MESSAGE_ID>"}'
```

Draft:

```bash
curl -s http://127.0.0.1:8000/gmail/analyze-and-create-draft \
  -H "Content-Type: application/json" \
  -d '{"message_id":"<GMAIL_MESSAGE_ID>"}'
```

## Jobs (polling) — przetwarzanie inboxu
To jest wersja pollingowa (bez webhooków Gmail push).

### POST /jobs/process-inbox
Uruchamia job przetwarzania ostatnich N wiadomości. Pomija wiadomości z labelem `AI/Processed`.

#### Zabezpieczenie (dla schedulera)
Ustaw w środowisku `JOB_SECRET` i wywołuj endpoint z nagłówkiem `X-Job-Secret`.

Przykład:

```bash
curl -s http://127.0.0.1:8000/jobs/process-inbox \
  -H "Content-Type: application/json" \
  -H "X-Job-Secret: <JOB_SECRET>" \
  -d '{"limit": 10, "query": "in:inbox newer_than:7d"}'
```

### Jak odpalać cyklicznie na Render (na razie ręcznie)
- Najprościej: zewnętrzny “uptime monitor / cron” który uderza w `POST /jobs/process-inbox` co X minut.
- Docelowo: Render cron/background worker (w kolejnym kroku).

## GitHub Actions — polling co 5 minut
Repo zawiera workflow `.github/workflows/process-inbox.yml`, który cyklicznie (co ~5 min) wykonuje `POST` na produkcyjny endpoint Render:
- `POST https://agencizc.onrender.com/jobs/process-inbox`

## Architektura: orchestrator + zespół agentów
Projekt jest przygotowany pod rozwój w kierunku wielu agentów (team-of-agents) bez zmiany publicznych endpointów.

### Warstwy (high-level)
- **API** (`app/api/routes/*`): endpointy HTTP (kompatybilne wstecz).
- **Orchestrator** (`app/orchestrator/email_orchestrator.py`): decyzja “który agent i w jakiej kolejności”.
- **Agenci** (`app/agents/team/*`):
  - `InboxAgent`: analiza maila (klasyfikacja + wstępny draft) — obecnie reuse istniejącego `EmailAgent`.
  - `DraftAgent`: finalizacja/validacja draftu (na razie pass-through).
  - `ResearchAgent`: stub z gotowym kontraktem (na razie bez prawdziwego web search).

### Jak dodać kolejnego agenta
1. Dodaj plik w `app/agents/team/` implementujący kontrakt z `app/agents/team/contracts.py` (`name` + `run()`).
2. Dodaj routing w `EmailOrchestrator.handle_email()` (kiedy i z jakim inputem agent ma być wywołany).
3. Dopisz test routingu w `tests/` (spy/stub agent + asercje wywołań).

### Pierwszy realny workflow multi-agent (Inbox + Research + Draft)
- **Krok 1 (InboxAgent)**: analiza maila (kategoria/priorytet/summary + wstępny draft).
- **Krok 2 (routing orchestratora)**:
  - proste maile → `InboxAgent` + `DraftAgent`
  - maile “biznesowo złożone” (oferta/partnerstwo/współpraca, `category=sales_inquiry|partnership`, słowa-klucze) → `InboxAgent` + `ResearchAgent` + `DraftAgent`
- **Krok 3 (ResearchAgent)**: bez web searchu — generuje `research_summary`, listę brakujących informacji i rekomendowane pytania doprecyzowujące.
- **Krok 4 (DraftAgent)**: buduje bardziej konkretny draft z lepszą strukturą i pytaniami doprecyzowującymi.

## Approval flow (draft-first, human-in-the-loop)
System **nigdy nie wysyła maili automatycznie**. Każdy utworzony draft trafia do kolejki zatwierdzeń.

### Statusy draftów
- `pending_review` — oczekuje na decyzję człowieka
- `approved` — zatwierdzony (gotowy pod przyszły krok “send”)
- `rejected` — odrzucony
- `sent` — zarezerwowane pod przyszłe wysyłanie

### Endpointy developerskie
- `GET /drafts/pending` — lista draftów do przejrzenia
- `POST /drafts/{draft_id}/approve` — zatwierdź draft
- `POST /drafts/{draft_id}/reject` — odrzuć draft
- `POST /drafts/{draft_id}/send` — wyślij draft (**tylko jeśli status=approved**)

### Jak to działa (high-level)
1. Email wpada → orchestrator uruchamia agentów.
2. Jeśli powstaje draft (np. przez `POST /gmail/analyze-and-create-draft` albo job polling), Gmail tworzy draft i zwraca `draft_id`.
3. Backend zapisuje draft w repozytorium z `status=pending_review`.
4. Człowiek przegląda `GET /drafts/pending` i podejmuje decyzję approve/reject.
5. Jeśli `approved`, można wysłać draft przez `POST /drafts/{draft_id}/send` (status przechodzi na `sent`).

Uwaga: repozytorium jest na razie **in-memory (process-local)** — docelowo do podmiany na DB bez zmian w API.

### Jak ustawić GitHub Secret
1. Wejdź w repo na GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Kliknij **New repository secret**
3. Nazwa: `JOB_SECRET`
4. Wartość: taka sama jak `JOB_SECRET` ustawiony na Render (wartość do nagłówka `X-Job-Secret`)

### Jak odpalić workflow ręcznie
1. GitHub → zakładka **Actions**
2. Wybierz workflow **Process Inbox (polling)**
3. Kliknij **Run workflow**

### Jak sprawdzić logi i czy działa co 5 minut
- GitHub → **Actions** → wybierz ostatnie uruchomienie workflow → sprawdź logi kroku **Call /jobs/process-inbox**
- Workflow uruchamia się także z `schedule` (cron). Uwaga: harmonogram GitHub Actions jest **best-effort** (może mieć opóźnienia), ale będzie wykonywał wywołania cyklicznie.
