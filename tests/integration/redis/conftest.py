"""Tests under this directory touch a real local Redis, not Postgres.

Overrides the parent `tests/integration/conftest.py`'s
`_guard_against_shared_database` fixture (autouse, session-scoped) with a
no-op: that guard exists to protect the shared Supabase Postgres instance
from stray writes, which doesn't apply here -- Redis is pure ephemeral
cache with nothing durable and no shared/hosted instance in play. Without
this override, tests here would be blanket-skipped by the Postgres guard
even though they never touch Postgres.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _guard_against_shared_database() -> None:
    pass
