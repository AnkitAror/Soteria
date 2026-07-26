"""Redis-cached per-user scoring history, so `fetch_scoring_inputs`
(transaction_history.py) doesn't re-fetch a user's entire transaction
history from Postgres and re-normalize/re-categorize every past row on
every single new transaction.

`build_history_stats`/`compute_scores` (services/scoring.py) are
deliberately untouched by this: they stay pure functions over a plain
`list[TransactionFeatures]`, exactly as before. This module only changes
where that list comes from -- Redis on a cache hit, Postgres (unchanged
query) on a miss, with the miss path populating the cache for next time.

Data layout:
    scoring:history:{user_id}   HASH   field=str(transaction_id) -> JSON(TransactionFeatures)
    scoring:subs:{user_id}      SET    members = normalized_merchant strings

A HASH keyed by transaction_id (not a LIST) makes appends idempotent via a
single atomic HSETNX -- a Celery task retried after a crash mid-task can
safely call append_to_history twice for the same transaction. It also lets
a reader exclude its own transaction_id from a residual cache entry, the
same way the Postgres query excludes it via `Transaction.id != transaction.id`.

The TTL is a backstop against any invalidation path not yet identified --
not the primary correctness mechanism. That's the explicit
invalidate_history() calls in plaid/transactions.py and
analysis/subscriptions.py, made whenever a transaction affecting a user's
history is modified, removed, or retroactively linked to a subscription.
"""

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import cast

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.core.config import get_settings
from soteria.core.redis_client import get_redis_client


def _history_key(user_id: uuid.UUID) -> str:
    return f"scoring:history:{user_id}"


def _subs_key(user_id: uuid.UUID) -> str:
    return f"scoring:subs:{user_id}"


def _encode_features(features: TransactionFeatures) -> str:
    return json.dumps(
        {
            "amount": str(features.amount),
            "transaction_date": features.transaction_date.isoformat(),
            "normalized_merchant": features.normalized_merchant,
            "normalized_category": features.normalized_category,
        }
    )


def _decode_features(raw: str) -> TransactionFeatures:
    data = json.loads(raw)
    return TransactionFeatures(
        amount=Decimal(data["amount"]),
        transaction_date=date.fromisoformat(data["transaction_date"]),
        normalized_merchant=data["normalized_merchant"],
        normalized_category=data["normalized_category"],
    )


def get_cached_history(
    user_id: uuid.UUID, *, exclude_transaction_id: uuid.UUID
) -> tuple[list[TransactionFeatures], set[str]] | None:
    """None on cache miss. On hit, excludes exclude_transaction_id's own
    entry but does NOT apply the caller's as-of-date filter -- entries
    accumulate in processing order, not chronological order, so
    transaction_history.py::fetch_scoring_inputs re-filters by date itself.
    """
    if not get_settings().scoring_cache_enabled:
        return None

    client = get_redis_client()
    history_key = _history_key(user_id)
    if not client.exists(history_key):
        return None

    exclude_field = str(exclude_transaction_id)
    raw_entries = cast(dict[str, str], client.hgetall(history_key))
    features = [
        _decode_features(raw) for field, raw in raw_entries.items() if field != exclude_field
    ]
    subscription_merchants = cast(set[str], client.smembers(_subs_key(user_id)))
    return features, subscription_merchants


def store_history(
    user_id: uuid.UUID,
    features_by_id: list[tuple[uuid.UUID, TransactionFeatures]],
    subscription_merchants: set[str],
) -> None:
    """Bulk-populate on cache miss, keyed by real transaction_id (not a
    synthetic index) so two near-simultaneous cache-miss populations for
    the same user converge instead of duplicating entries.

    A user with zero prior transactions never produces a cache entry here
    (Redis auto-deletes an empty HASH/SET, and HSET/SADD reject empty
    input) -- every such call stays a miss, which is the cheapest possible
    Postgres query anyway, so this is harmless.
    """
    if not get_settings().scoring_cache_enabled:
        return

    client = get_redis_client()
    ttl = get_settings().scoring_cache_ttl_seconds

    if features_by_id:
        history_key = _history_key(user_id)
        mapping = {str(txn_id): _encode_features(features) for txn_id, features in features_by_id}
        client.hset(history_key, mapping=mapping)
        client.expire(history_key, ttl)

    if subscription_merchants:
        subs_key = _subs_key(user_id)
        client.sadd(subs_key, *subscription_merchants)
        client.expire(subs_key, ttl)


def append_to_history(
    user_id: uuid.UUID, transaction_id: uuid.UUID, features: TransactionFeatures
) -> None:
    """Called after a transaction is newly scored. No-op if no cache entry
    exists yet for this user -- don't bootstrap a partial cache from a
    single append, let the next full miss populate it properly via
    store_history. Idempotent: HSETNX is a no-op if this transaction_id was
    already appended, so a Celery task redelivered after a crash mid-task
    can safely call this twice.
    """
    if not get_settings().scoring_cache_enabled:
        return

    client = get_redis_client()
    history_key = _history_key(user_id)
    if not client.exists(history_key):
        return

    client.hsetnx(history_key, str(transaction_id), _encode_features(features))


def invalidate_history(user_id: uuid.UUID) -> None:
    """Deletes both keys for a user. Called whenever a transaction affecting
    their history is modified, removed, or retroactively linked to a
    subscription -- always AFTER the Postgres write commits, never before,
    so a concurrent cache-miss reader can't re-read stale pre-commit state
    and repopulate the cache with the staleness this is meant to clear.
    """
    get_redis_client().delete(_history_key(user_id), _subs_key(user_id))
