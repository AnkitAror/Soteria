"""Shared Redis client — one connection pool per process, reused across
webhook dedup, the scoring cache, and anything else that needs Redis
outside of Celery's own broker/backend connections.
"""

from functools import lru_cache

import redis

from soteria.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
