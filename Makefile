.PHONY: install lint format typecheck test up down worker beat api ci migrate migrate-autogenerate migrate-down

# Keep the venv out of ~/Desktop: on this machine Desktop is iCloud-synced,
# and iCloud's background sync races with uv's rapid venv writes and
# corrupts it (observed as broken symlinks / silent import failures).
export UV_PROJECT_ENVIRONMENT := $(HOME)/.venvs/soteria

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

test:
	uv run pytest

up:
	docker compose up -d --build

down:
	docker compose down

worker:
	# --concurrency kept conservative even on the transaction-mode pooler
	# (port 6543) — see the comment on the worker service in docker-compose.yml.
	uv run celery -A soteria.worker.celery_app worker --loglevel=info --concurrency=4

beat:
	uv run celery -A soteria.worker.celery_app beat --loglevel=info

api:
	uv run uvicorn soteria.api.main:app --reload

ci: lint typecheck test

migrate:
	uv run alembic upgrade head

migrate-autogenerate:
	uv run alembic revision --autogenerate -m "$(m)"

migrate-down:
	uv run alembic downgrade -1
