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
