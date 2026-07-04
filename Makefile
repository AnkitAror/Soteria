.PHONY: install lint format typecheck test up down worker ci

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
	docker compose up -d

down:
	docker compose down

worker:
	uv run celery -A soteria.worker.celery_app worker --loglevel=info

ci: lint typecheck test
