# Soteria Engineering Brief

Soteria is an event-driven financial intelligence platform with a FastAPI
backend, a Vite/React web client, Supabase persistence/auth, and a
Celery-based transaction enrichment pipeline with an LLM-assisted spending
assistant.

This document is intentionally concise and operationally focused.

## 1) System Scope

Product pillars:

- **Transaction Enrichment & Scoring**: per-transaction normalization,
  categorization, subscription linking, and heuristic fraud/anomaly/
  behavioral/smart-purchase scoring.
- **Insight Generation**: 12 rule-based checks across spending, subscription,
  cash-flow, and behavioral categories, deduplicated and expired
  automatically as the underlying facts change.
- **Subscription Detection**: recurring outflow-stream discovery via
  Plaid's `/transactions/recurring/get`, decoupled from per-transaction
  processing.
- **SoteriaChat**: a retrieval-and-SQL-grounded spending assistant — no
  free-form LLM database access, ever.
- **Account Management**: Plaid Link, webhook-driven item status
  (`active`/`login_required`/`error`/`revoked`), update-mode relink, unlink.

Primary backend objectives:

- Keep every read/write scoped to the requesting user — no cross-tenant
  leakage, enforced at the application layer (see §7).
- Keep sync and scoring idempotent: re-running a sync or a task must never
  duplicate rows or double-count anything.
- Never let the chat assistant execute arbitrary SQL — generated queries are
  validated against an AST allow-list before they ever touch the database.
- Degrade safely under dependency failures: a failed LLM call or a rejected
  generated query should produce a graceful fallback answer, not a 500.

## 2) Core Stack

- **API**: FastAPI (Python 3.12+, dependency/env management via `uv`)
- **Task queue**: Celery + Redis (broker + result backend), Celery Beat for
  the one scheduled job (insight fan-out)
- **Data/Auth**: Supabase Postgres + pgvector, Supabase Auth (JWT verified
  against the project's JWKS — no shared secret)
- **Scoring**: heuristic/statistical, not trained models — merchant/category
  normalization, frequency and deviation-based fraud/anomaly/behavioral/
  smart-purchase scores. There is no ML training pipeline in this codebase.
- **Chat/LLM**: Google Gemini (`gemini-flash-latest` for intent
  classification, NL→SQL generation, and answer synthesis;
  `gemini-embedding-001`, 1536-dim, for pgvector retrieval embeddings) and
  `sqlglot` for AST-level SQL validation.
- **External services**: Plaid (Link, `/transactions/sync`,
  `/transactions/recurring/get`, webhooks), Google Gemini API.

## 3) Backend Architecture

Request path layering:

1. Route handlers (`api/routers/*.py`) validate input and compose calls into
   the domain layer.
2. `core/auth.get_current_user_id` verifies the Supabase JWT and resolves it
   to an internal `users.id`, auto-provisioning the row on first sight.
3. Domain/persistence functions run user-scoped queries through a
   short-lived `SessionLocal()` — one session per logical unit of work, not
   one per DB call (see §9 for why this mattered).
4. Celery tasks (`worker/tasks/*.py`) do the same, loading fresh ORM state
   from an id rather than crossing process boundaries with live objects.

Security model:

- Bearer token required on every `/api/*` route (`/plaid/webhook` is
  verified separately, against Plaid's own signing key, when
  `PLAID_WEBHOOK_VERIFICATION_ENABLED=true`).
- JWT verified via `PyJWKClient` against Supabase's
  `/auth/v1/.well-known/jwks.json` (ES256/RS256) — no static secret to
  rotate or leak.
- Every query is explicitly filtered by `user_id`; there is **no Postgres
  Row-Level Security** in this project — isolation is enforced entirely at
  the application layer.
- The chat assistant's LLM-generated SQL gets a second, independent layer of
  isolation on top of that: it runs only against four read-only Postgres
  views (`v_transactions`, `v_subscriptions`, `v_insights`,
  `v_bank_accounts`) that filter on a session-local
  `current_setting('app.chat_user_id')`, and `chat/orchestration/
  sql_safety.py` rejects anything that isn't a single `SELECT` against that
  allow-list before it's ever executed.

Idempotency model:

- `transactions` upsert on Plaid's own `plaid_transaction_id` (unique
  constraint).
- Webhook events deduplicated via a Redis `SETNX` claim keyed on
  `item_id:webhook_code` (300s TTL) — composite-keyed where Plaid nests the
  real event inside a generic wrapper (e.g. `ITEM_LOGIN_REQUIRED` arrives as
  a generic `ITEM`/`ERROR` webhook with the real code in `error.error_code`).
- `insights` upsert on `(user_id, type, identity_key, value_signature)` —
  a still-true finding gets its expiry extended rather than duplicated; a
  materially changed one supersedes the old row instead of waiting out its
  natural expiry.
- `embeddings` upsert on `(user_id, object_type, object_id)`, skipped
  entirely if `content_hash` is unchanged since the last embed.

## 4) Runtime Flows

**Authentication**
Client sends the Supabase session's access token as a bearer header → JWT
verified against JWKS → resolved/auto-provisioned to an internal `users`
row → all downstream queries scoped to that `user_id`.

**Bank Sync**
Plaid webhook arrives → `/plaid/webhook` validates the payload and
Redis-dedupes the event → `sync_plaid_item` (Celery) dispatched → calls
`/transactions/sync` with the item's stored cursor → added/modified
transactions upserted, removed ones soft-deleted, cursor persisted → each
newly added transaction dispatches its own `process_transaction`, and any
adds also dispatch `detect_subscriptions_task`.

**Transaction Enrichment & Scoring**
`process_transaction` (Celery): fetch the transaction → normalize merchant
→ categorize → link against an already-known active subscription → fetch
history → compute heuristic scores → persist analysis. Runs in one DB
session end to end (see §9).

**Insight Generation**
`POST /api/insights/generate` (on demand) or Celery Beat's interval fan-out
(`INSIGHTS_GENERATION_INTERVAL_MINUTES`, default 360) → 12 rules evaluated
against aggregated spending/subscription/cash-flow data → `upsert_insight`
dedupes/refreshes/supersedes → new or changed insights are embedded
(Gemini) for chat retrieval.

**Chat Retrieval (RAG + NL→SQL)**
Question submitted → `intent_classification` decides, per question, whether
SQL generation and/or pgvector retrieval are actually needed (not run
unconditionally) → if needed, SQL is generated against a live
`information_schema`-introspected view schema, validated by `sqlglot`, and
executed with `set_config('app.chat_user_id', ...)` scoping → if needed,
the question is embedded and matched against embedded insights via
pgvector cosine distance → `answer_synthesis` produces the answer plus
structured citations (only ever citing items it was actually given) →
persisted to `chat_messages`, including on the `sql_generated` and
`citations_json` columns.

## 5) Scheduler Operations

Scheduler characteristics:

- Celery Beat runs as its own container/process (`make beat` natively,
  `beat` service in `docker-compose.yml`), separate from the worker.
- `task_acks_late=True` + `task_reject_on_worker_lost=True`: a task is
  redelivered, not lost, if its worker dies mid-execution.
- Every task declares `autoretry_for=(Exception,)`,
  `retry_backoff=True`/`retry_backoff_max=600`, `retry_jitter=True`; a
  default `max_retries=3` applies to any task via `self.retry()`.

Scheduled jobs:

- `insights.fan_out_generation`: every `INSIGHTS_GENERATION_INTERVAL_MINUTES`
  (default 360 = 6 hours). This is the **only** Beat-scheduled job — there is
  no periodic sync (sync is entirely webhook/event-driven) and no model
  retraining job (scoring is heuristic, not a trained model).

There is no email/notification system on job lifecycle events — job
outcomes are visible via container logs (`docker compose logs worker|beat`)
only.

## 6) API Surface (Critical Endpoints)

Legacy/smoke-test:

- `GET /` — a static Plaid Link sandbox test page predating the real
  frontend; not a health check, not part of the product surface.

Auth:

- `GET /api/me`

Plaid:

- `POST /api/plaid/link-token`
- `POST /api/plaid/exchange`
- `POST /api/plaid/accounts`
- `POST /api/plaid/transactions/sync`
- `POST /plaid/webhook`

Dashboard & transactions:

- `GET /api/accounts`
- `GET /api/dashboard/spending-summary`
- `GET /api/dashboard/spending-by-category`
- `GET /api/transactions` (`limit`, `offset`, `category`, `search`)

Insights:

- `GET /api/insights`
- `POST /api/insights/generate`
- `POST /api/insights/{insight_id}/dismiss`

Subscriptions:

- `GET /api/subscriptions`

Account management:

- `GET /api/institutions`
- `POST /api/institutions/{plaid_item_id}/relink-token`
- `POST /api/institutions/{plaid_item_id}/relink-complete`
- `DELETE /api/institutions/{plaid_item_id}`

Chat:

- `GET /api/chat/usage`
- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}/messages`
- `POST /api/chat/sessions/{session_id}/messages`
- `PATCH /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`

## 7) Data Contracts

Tables (one SQLAlchemy model per table, `src/soteria/db/models/`):

`users`, `plaid_items`, `bank_accounts`, `transactions`,
`transaction_analysis`, `subscriptions`, `merchant_profiles`, `insights`,
`embeddings`, `chat_sessions`, `chat_messages`, `gemini_usage_daily`.

Important `transactions` columns:

`user_id`, `account_id`, `plaid_transaction_id`, `merchant_id`,
`merchant_name`, `description`, `amount`, `currency`, `transaction_date`,
`authorized_date`, `pending`, `category`, `payment_channel`,
`location_json`, `removed_at` (soft delete).

Chat-safety views (read-only, added by the `add_chat_views_and_citations`
migration): `v_transactions`, `v_subscriptions`, `v_insights`,
`v_bank_accounts` — each excludes sensitive columns (no
`plaid_access_token`, no raw Plaid IDs) and filters on
`current_setting('app.chat_user_id')`.

Isolation requirement: **application-level `user_id` scoping, not Postgres
RLS.** Every domain query filters explicitly; the chat SQL path adds the
view + AST-validation layer described in §3. If RLS is added later, it
would be additive, not a replacement for the existing checks.

## 8) Frontend Data-Freshness Policy (Current)

There is no persistent client-side cache layer (no React Query, no service
worker, no local cache invalidation bus) — this is simpler than a typical
production SPA cache policy, by design at current scale:

- Every page fetches on mount (`useEffect` + `apiFetch`).
- Mutating actions (dismiss an insight, generate insights, send a chat
  message, relink/unlink an institution) refetch the affected list
  afterward rather than patching local state speculatively, with one
  exception: the chat page optimistically appends the user's own message
  immediately, before the server responds.
- There is no polling or push mechanism for out-of-band changes (e.g. a
  webhook-driven sync completing while a tab is open) — the user has to
  revisit or refresh the affected page to see it. This is a known, accepted
  gap, not an oversight (see §9).

## 9) Reliability and Failure Modes

Known constraints:

- Celery worker concurrency is capped at 4 (prefork), a deliberately
  conservative default even after moving to Supabase's higher-capacity
  transaction-mode connection pooler — not a hard ceiling, just untested
  further.
- `psycopg3`'s default server-side statement auto-prepare is incompatible
  with PgBouncer transaction-mode pooling (`DuplicatePreparedStatement`
  under sustained load, confirmed live) — worked around via
  `connect_args={"prepare_threshold": None}` in `db/session.py`. Anyone
  touching connection pooling here should know this constraint exists.
- External dependency latency dominates the sync path: a Plaid
  `/transactions/sync` round trip runs ~0.7–0.8s regardless of how fast our
  own code is; the enrichment/scoring stage itself runs ~0.3s.
- Gemini's free tier caps out fast (as low as 20 requests/day observed on
  this project's key) — `chat/usage.py` self-tracks a daily counter and
  surfaces it via `GET /api/chat/usage`, since Google's API doesn't expose
  real quota-remaining. It's an approximation, not authoritative.
- No live push/streaming to the client and no CI/CD pipeline exist yet —
  both are known, deferred gaps, not silent omissions.

Operational expectations:

- Fail closed on the auth path: a bad/missing/expired token is a 401, full
  stop.
- Fail soft on the chat pipeline: a rejected or failed generated SQL query
  degrades to an answer without that data (still with whatever retrieved
  context is available), never a 500.
- Never log secrets: `plaid_access_token` is encrypted at rest
  (`cryptography`/Fernet) and never logged in plaintext; API keys are read
  from settings, never printed.
- Docker dev-mode only (hot-reload, bind-mounted source) — no production
  build/deploy configuration exists yet.

## 10) Configuration

Required backend environment variables:

- `DATABASE_URL` — Supabase's **transaction-mode pooler** (port 6543), not
  the session-mode pooler (5432) or a direct connection; see §9.
- `PLAID_CLIENT_ID`, `PLAID_SECRET`
- `ENCRYPTION_KEY` — Fernet key for `plaid_access_token` at rest
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- `GEMINI_API_KEY` — the app runs fine without it; only `/api/chat/*`
  degrades (errors on send)

Optional backend environment variables (all have defaults in
`core/config.py`):

- `ENVIRONMENT` (default `local`), `LOG_LEVEL` (default `INFO`)
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (default to
  `localhost`; overridden to the `redis` service name in Docker Compose)
- `PLAID_ENV` (default `sandbox`)
- `PLAID_WEBHOOK_VERIFICATION_ENABLED` (default `false`)
- `PLAID_WEBHOOK_URL` (default blank — webhooks are simply skipped if unset)
- `INSIGHTS_GENERATION_INTERVAL_MINUTES` (default `360`)
- `GEMINI_CHAT_MODEL` (default `gemini-flash-latest`)
- `GEMINI_EMBEDDING_MODEL` (default `gemini-embedding-001`)
- `GEMINI_DAILY_REQUEST_LIMIT` (default `20`)

Frontend (`frontend/.env`): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
`VITE_API_BASE_URL`.

## 11) Local Runbook

Full stack (recommended — containerizes everything except the database,
which is hosted on Supabase):

```bash
cp .env.example .env                    # fill in the required values from §10
cp frontend/.env.example frontend/.env  # fill in the Supabase/API values
make up                                 # docker compose up -d --build: redis, api, worker, beat, frontend
make down                    # tear it all down
```

Backend (native, e.g. to attach a debugger — three separate terminals):

```bash
make install
make api       # uvicorn --reload
make worker    # celery worker
make beat      # celery beat
```

Frontend (native):

```bash
cd frontend
npm install
npm run dev
```

Common workflows: `make lint`, `make format`, `make typecheck`, `make test`,
`make migrate`, `make ci`.
