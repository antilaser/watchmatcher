# watchmatch

AI assistant for filtering messages from watch-trading chat groups (WhatsApp first), classifying buy/sell intent, extracting structured trade data, matching offers to requests, and surfacing profitable opportunities for human review.

> Codename: **Rolex**. Domain: any high-end watch brand.

## Stack

- Python 3.12, FastAPI, async SQLAlchemy 2.x, Alembic
- PostgreSQL 16 + pgvector
- Redis + arq (asyncio job queue)
- OpenAI (LLM fallback only)
- Telegram bot for alerts
- Docker Compose for local dev

## Quick start

```bash
cp .env.example .env
# fill OPENAI_API_KEY, TELEGRAM_BOT_TOKEN if needed
docker compose up --build
```

API:        http://localhost:8000/docs
Health:     http://localhost:8000/health

### Local dev without Docker

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1   # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
arq app.workers.arq_worker.WorkerSettings
```

## Architecture

Pipeline (see SPEC §10):

1. Ingestion (provider abstraction: webhook, fake, future Baileys)
2. Raw storage + dedupe
3. Rule-based classification + extraction
4. LLM fallback when confidence low
5. Watch normalization (catalog + aliases + fuzzy)
6. Sell/Buy entity creation
7. Matching engine + profit calc
8. Alert delivery (Telegram + dashboard) + human review

## Feeding messages in

Two providers shipped:

- `FakeProvider` — reads JSON fixtures, used in tests and seeding
- `WebhookProvider` — `POST /api/v1/ingest/webhook` with HMAC-SHA256 in `X-Signature`

Run any external WhatsApp scraper (Baileys, whatsapp-web.js, Whapi.cloud) and POST messages to the webhook. The backend does not depend on any specific WA library.

## Tests

```bash
pytest
```

## Layout

See `app/` — modular by domain (parsing, normalization, matching, alerts, review, ingestion).
