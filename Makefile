.PHONY: install lint format typecheck test up down worker ci

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
