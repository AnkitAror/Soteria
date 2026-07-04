# Soteria

Event-driven financial intelligence platform.

## Stack

- Python 3.12+, managed with [uv](https://docs.astral.sh/uv/)
- Celery + Redis for event-driven task processing (scaffolded; no tasks yet)
- Postgres + pgvector, and an API layer, are planned but not yet implemented

## Getting started

```bash
uv sync
cp .env.example .env
docker compose up -d      # postgres + redis
make test
```

Run `make` targets for common workflows: `lint`, `format`, `typecheck`, `test`, `worker`, `ci`.

## Layout

```
src/soteria/
├── core/           # config, logging, security, exceptions, shared utils
├── db/             # SQLAlchemy base/session + per-table models (schema in references/db_schema.md)
├── worker/         # Celery app, tasks, pipelines
├── plaid/          # Plaid item linking, transaction sync, webhooks
├── analysis/       # fraud/spending/behavioral scoring
├── subscriptions/  # subscription detection
├── insights/       # insight generation
└── chat/           # RAG-backed chat (rag, services, orchestration)
```

## Status

This is a structure-and-tooling skeleton. Deliberately deferred to later passes:
DB models/migrations, the API layer, Celery task implementations, and all domain
business logic.
