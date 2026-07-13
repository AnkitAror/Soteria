"""Shared fixtures for integration tests — these touch a real Postgres database.

Run with DATABASE_URL pointed at a local/disposable database, e.g.:

    DATABASE_URL=postgresql://soteria:soteria@localhost:5432/soteria uv run pytest tests/integration

A session-scoped guard refuses to run if DATABASE_URL looks like the shared
Supabase instance configured in .env, so these tests can never accidentally
create/delete rows there.
"""

import uuid
from collections.abc import Iterator

import pytest

from soteria.core.config import get_settings
from soteria.db.models.insights import Insight
from soteria.db.models.subscriptions import Subscription
from soteria.db.models.users import User
from soteria.db.session import SessionLocal


@pytest.fixture(scope="session", autouse=True)
def _guard_against_shared_database() -> None:
    """Skip (not abort the whole session — a plain `make test` with no
    DATABASE_URL override must still run tests/unit/) if DATABASE_URL looks
    like the shared Supabase instance from .env."""
    url = get_settings().database_url
    if "supabase" in url:
        pytest.skip(
            "Refusing to run integration tests against what looks like the shared "
            "Supabase database (DATABASE_URL contains 'supabase'). Point DATABASE_URL "
            "at a local/disposable Postgres instance first, e.g.\n"
            "  DATABASE_URL=postgresql://soteria:soteria@localhost:5432/soteria"
        )


@pytest.fixture
def test_user_id() -> Iterator[uuid.UUID]:
    with SessionLocal() as session:
        user = User(email=f"insights-test-{uuid.uuid4()}@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    yield user_id

    with SessionLocal() as session:
        session.query(Insight).filter(Insight.user_id == user_id).delete()
        session.query(Subscription).filter(Subscription.user_id == user_id).delete()
        session.query(User).filter(User.id == user_id).delete()
        session.commit()
