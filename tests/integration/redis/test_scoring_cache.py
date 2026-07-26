"""Integration tests for scoring_cache.py against a real local Redis --
the same instance already used by Celery's broker and webhook_dedup.py.

Redis here is pure ephemeral cache: unlike tests/integration/conftest.py's
Postgres guard (which protects the shared Supabase instance from stray
writes), there's no shared/hosted Redis in play and nothing durable lives
here, so no equivalent data-loss guard is needed -- only a
reachability check, so `make test` without a running local Redis skips
cleanly instead of failing with a raw connection error.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
import redis

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.scoring_cache import (
    append_to_history,
    get_cached_history,
    invalidate_history,
    store_history,
)
from soteria.core.redis_client import get_redis_client


@pytest.fixture(scope="session", autouse=True)
def _skip_if_redis_unreachable() -> None:
    try:
        get_redis_client().ping()
    except redis.ConnectionError:
        pytest.skip("No local Redis reachable at REDIS_URL -- skipping scoring_cache tests.")


@pytest.fixture
def user_id() -> Iterator[uuid.UUID]:
    generated = uuid.uuid4()
    yield generated
    invalidate_history(generated)


def _features(amount: str = "10.00", merchant: str = "Merchant") -> TransactionFeatures:
    return TransactionFeatures(
        amount=Decimal(amount),
        transaction_date=date(2026, 7, 1),
        normalized_merchant=merchant,
        normalized_category="Food",
    )


def test_miss_returns_none(user_id: uuid.UUID) -> None:
    result = get_cached_history(user_id, exclude_transaction_id=uuid.uuid4())

    assert result is None


def test_store_then_get_round_trips(user_id: uuid.UUID) -> None:
    txn_id = uuid.uuid4()
    features = _features()
    store_history(user_id, [(txn_id, features)], {"Streamflix"})

    result = get_cached_history(user_id, exclude_transaction_id=uuid.uuid4())

    assert result is not None
    cached_features, subscription_merchants = result
    assert cached_features == [features]
    assert subscription_merchants == {"Streamflix"}


def test_get_excludes_own_transaction_id(user_id: uuid.UUID) -> None:
    txn_a, txn_b = uuid.uuid4(), uuid.uuid4()
    store_history(user_id, [(txn_a, _features("1")), (txn_b, _features("2"))], set())

    result = get_cached_history(user_id, exclude_transaction_id=txn_a)

    assert result is not None
    features, _ = result
    assert len(features) == 1
    assert features[0].amount == Decimal("2")


def test_append_to_nonexistent_cache_is_a_true_noop(user_id: uuid.UUID) -> None:
    append_to_history(user_id, uuid.uuid4(), _features())

    assert get_cached_history(user_id, exclude_transaction_id=uuid.uuid4()) is None


def test_append_is_idempotent_first_write_wins(user_id: uuid.UUID) -> None:
    txn_id = uuid.uuid4()
    store_history(user_id, [(uuid.uuid4(), _features("1"))], set())

    first = _features("5", merchant="First")
    second = _features("999", merchant="Second")
    append_to_history(user_id, txn_id, first)
    append_to_history(user_id, txn_id, second)  # must not clobber

    result = get_cached_history(user_id, exclude_transaction_id=uuid.uuid4())
    assert result is not None
    features, _ = result
    assert first in features
    assert second not in features


def test_invalidate_deletes_both_keys(user_id: uuid.UUID) -> None:
    store_history(user_id, [(uuid.uuid4(), _features())], {"Streamflix"})

    invalidate_history(user_id)

    assert get_cached_history(user_id, exclude_transaction_id=uuid.uuid4()) is None


def test_store_history_sets_a_ttl(user_id: uuid.UUID) -> None:
    store_history(user_id, [(uuid.uuid4(), _features())], set())

    ttl = get_redis_client().ttl(f"scoring:history:{user_id}")

    assert ttl > 0
