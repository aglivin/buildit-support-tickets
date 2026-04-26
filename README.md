# Support Ticket Triage API

## What this is

A FastAPI service that accepts support tickets, sends them to GPT-4o-mini for classification and summarisation, and stores the results in Postgres. Built as a take-home case study. The stack is Python 3.11 / FastAPI / SQLAlchemy 2.0 async / asyncpg / Alembic / Docker.

## Run it locally

1. Copy the env template and add your OpenAI key:
   ```bash
   cp .env.example .env
   # open .env and set OPENAI_API_KEY=sk-proj-...
   ```
2. Start the stack:
   ```bash
   docker compose up --build
   ```
   Alembic migrations run automatically before the app starts — no manual setup needed.
3. Open the interactive docs: http://localhost:8000/docs

## Environment variables

| Variable | What it does | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for ticket enrichment | *(required)* |
| `DATABASE_URL` | Async Postgres connection string | `postgresql+asyncpg://postgres:postgres@localhost:5433/buildit` |
| `LLM_MODEL` | Model used for classification | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | Hard timeout on the sync enrichment call | `5.0` |
| `DEDUP_WINDOW_MINUTES` | Window in which identical tickets dedupe | `5` |

`DATABASE_URL` in `.env.example` points at `localhost:5433` (the host-facing port). Inside docker-compose the `api` service overrides it to `db:5432` automatically — you don't need to change anything.

## API endpoints

| Method | Path | What it does |
|---|---|---|
| `POST` | `/tickets` | Create a ticket; returns enriched record (`201`) or `202` if LLM timed out |
| `GET` | `/tickets` | List tickets with optional filters and pagination |
| `GET` | `/tickets/{id}` | Fetch a single ticket by UUID |
| `GET` | `/healthz` | Health check |

### POST /tickets

```bash
curl -X POST http://localhost:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Charged twice for October subscription",
    "body": "I see two charges of €49 on my card from Oct 3. Please refund one.",
    "customer_email": "anna@example.com"
  }'
```

Returns `201 Created` with the enriched ticket. If the LLM took longer than `LLM_TIMEOUT_SECONDS`, returns `202 Accepted` — the ticket is saved with `enrichment_status: pending` and enrichment finishes in the background.

```bash
curl -X POST http://localhost:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "PDF export crashes on invoices over 50 pages",
    "body": "Exporting an invoice with 60 line items throws a 500. Happens every time. Stack trace in attachment.",
    "customer_email": "ops@enterprise.com"
  }'
```

### GET /tickets

Filters: `category` (`billing` | `bug` | `feature_request` | `account` | `other`), `priority` (`low` | `medium` | `high` | `urgent`), `since` (ISO-8601 datetime). Pagination: `limit` (default 20, max 100), `offset`.

```bash
curl "http://localhost:8000/tickets?category=billing&priority=high&limit=10"
curl "http://localhost:8000/tickets?since=2026-04-01T00:00:00Z"
```

Submitting the same ticket (same email + body, whitespace-normalised) within 5 minutes returns `200 OK` with the existing record. No second LLM call is made.

## Architecture decisions

**1. Sync LLM call with 5 s timeout, fall back to background task on timeout**

**What:** `enrich_ticket` wraps the OpenAI call in `asyncio.wait_for(..., timeout=5s)` ([enrichment.py:61–68](app/services/enrichment.py)). If it finishes in time the handler returns `201` with full enrichment. On `TimeoutError` the ticket is saved as `pending`, the handler returns `202 Accepted`, and `BackgroundTasks.add_task` finishes enrichment after the response is sent ([tickets.py:99–106](app/api/tickets.py)).

**Why:** sync-only blocks every request for the full LLM round-trip (~1–3 s p50, up to 10 s at p99). Pure async (decouple POST from LLM entirely) needs Redis + a separate worker service. The hybrid keeps p50 users whole while bounding POST latency for everyone else.

**Trade-off:** `BackgroundTasks` has no supervisor. A process restart mid-flight leaves the ticket `pending` forever — mitigated by the startup sweep in [`main.py:22–44`](app/main.py) that re-enqueues tickets older than 1 minute. For production the right fix is ARQ + Redis, which I deferred as out of scope here.

---

**2. Regex PII masking before sending to LLM; plaintext storage at rest**

**What:** `mask_for_llm` runs 5 regex passes over title and body before the OpenAI call — API keys (Anthropic, OpenAI, Stripe, AWS, long base64 blobs), IBANs, card-like digit sequences, email local parts (domain is kept as a priority signal), and phone numbers ([pii.py:22–34](app/services/pii.py)). `customer_email` as a field is never sent to the LLM at all. Tickets are stored as plaintext in Postgres.

**Why:** masking covers the most common accidental leaks without a dedicated NLP service. Plaintext DB storage is deliberate — app-level AES-GCM encryption with a key in env is security theatre: if an attacker has the DB dump they almost certainly have the env too. A real deployment would use pgcrypto or disk-level TDE backed by a secrets manager.

**Trade-off:** regex doesn't catch names, addresses, or national IDs. A paraphrased secret (e.g. "my key is A K I A...") would slip through. For production I'd add Microsoft Presidio.

---

**3. SHA-256 fingerprint dedup with a 5-minute lookup window**

**What:** `compute_fingerprint` hashes `(email_lower + whitespace-normalised body)` with SHA-256 ([dedup.py:12–15](app/services/dedup.py)). The optimistic path does a SELECT before INSERT. A `UNIQUE` constraint on `fingerprint` handles the race: on `IntegrityError` the handler rolls back and re-fetches the existing ticket ([tickets.py:74–83](app/api/tickets.py)).

**Why:** covers double-click submits and widget retries. The `UNIQUE` constraint makes it safe under concurrent requests without any locking. Returning `200` (rather than `409`) follows Stripe-style idempotency — the client always gets a valid ticket regardless of whether it was a duplicate.

**Trade-off:** exact-match only — a paraphrased duplicate is not caught. The constraint is global (no time-based partial index), so an identical ticket submitted a year later returns the old record rather than creating a new one. Acceptable here; a year-old identical complaint is the same complaint.

---

**4. FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic**

**What:** fully async stack — async FastAPI handlers, async SQLAlchemy sessions, asyncpg driver, `asyncio.wait_for` for the LLM timeout.

**Why:** the LLM call dominates latency. A sync WSGI server would block one thread per in-flight request during that window. Async lets a small process handle many concurrent tickets without thread-pool pressure.

**Trade-off:** SQLAlchemy's async session API is more verbose than the sync one (`await session.execute(select(...))` instead of `session.query(...)`). Alembic's `env.py` needs manual wiring for async connections — it doesn't do this out of the box.

---

**5. Single-table schema with native Postgres ENUMs and composite indexes**

**What:** one `tickets` table. `category`, `priority`, `sentiment`, and `enrichment_status` are Postgres `ENUM` types. Composite indexes on `(category, created_at)` and `(priority, created_at)` cover the two main query shapes in `GET /tickets`. A `UNIQUE` constraint on `fingerprint` enforces dedup at the DB layer.

**Why:** the only access patterns are filter-by-category + sort-by-date and filter-by-priority + sort-by-date. Composite indexes serve both directly without a full scan. ENUMs enforce valid values at the DB layer — no application-side validation needed for those columns.

**Trade-off:** adding a new category or priority value requires an `ALTER TYPE` migration, not just a code change. If the value set were expected to change frequently a lookup table would be more flexible.

## What I'd do with more time

- **Durable background queue (ARQ + Redis).** The current `BackgroundTasks` approach survives only within a single process lifetime. ARQ would give retries, dead-letter queues, and visibility into stuck jobs.
- **Semantic dedup with pgvector.** The current SHA-256 fingerprint misses paraphrased duplicates ("charged twice" vs "double billed"). Embedding similarity at query time would catch those.
- **Structured logging with structlog.** Right now logs are plain text with no correlation IDs. Adding `ticket_id` and `enrichment_status` to every log line would make incidents debuggable from logs alone.
- **Per-email rate limiting.** Nothing stops a single address from flooding `POST /tickets` and burning LLM budget. `slowapi` + Redis would handle this in a few lines.
- **Proper PII detection via Presidio.** The current 5-pass regex catches obvious patterns but misses names, addresses, and national IDs. Microsoft Presidio runs locally and covers a much wider surface.
