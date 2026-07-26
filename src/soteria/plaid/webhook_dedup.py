"""De-duplicate Plaid webhook deliveries.

Plaid delivers webhooks at-least-once and retries on non-200 responses or
timeouts, so the same event can arrive more than once. We use Redis SETNX
as an atomic idempotency lock, keyed on (item_id, webhook_code), with a TTL:
short enough that the same event type can legitimately fire again later
for a genuinely new update, long enough to absorb a retry burst for one
delivery attempt.
"""

from soteria.core.redis_client import get_redis_client

_DEDUP_TTL_SECONDS = 300


def claim_webhook_event(item_id: str, webhook_code: str) -> bool:
    """Returns True the first time an (item_id, webhook_code) pair is seen within the
    TTL window; False if it's a duplicate delivery that should be skipped."""
    key = f"plaid:webhook:{item_id}:{webhook_code}"
    return bool(get_redis_client().set(key, "1", nx=True, ex=_DEDUP_TTL_SECONDS))
