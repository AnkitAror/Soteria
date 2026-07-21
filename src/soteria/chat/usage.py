"""Approximates remaining Gemini free-tier quota.

Google's Generative Language API doesn't expose real-time quota-remaining;
the only concrete limit number this app has ever seen was in a 429 error's
message ("limit: 20, model: gemini-3.5-flash"). This is our own counter,
incremented by chat/gemini_client.py on every successful call, compared
against a configured daily limit (core/config.py's
gemini_daily_request_limit). It will drift from Google's real count if a
call is retried at the SDK/network layer, or if the account's actual quota
changes -- it's an approximation, not an authoritative reading.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text

from soteria.core.config import get_settings
from soteria.db.session import SessionLocal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageStatus:
    used: int
    limit: int
    remaining: int


def record_usage() -> None:
    """Best-effort: a failure here should never break the Gemini call it's
    tracking."""
    try:
        with SessionLocal() as session:
            session.execute(
                text(
                    """
                    INSERT INTO gemini_usage_daily (day, request_count)
                    VALUES (CURRENT_DATE, 1)
                    ON CONFLICT (day)
                    DO UPDATE SET request_count = gemini_usage_daily.request_count + 1
                    """
                )
            )
            session.commit()
    except Exception:
        logger.exception("Failed to record Gemini usage; continuing")


def get_usage_today() -> UsageStatus:
    limit = get_settings().gemini_daily_request_limit
    with SessionLocal() as session:
        used = session.execute(
            text("SELECT request_count FROM gemini_usage_daily WHERE day = CURRENT_DATE")
        ).scalar()
    used = used or 0
    return UsageStatus(used=used, limit=limit, remaining=max(limit - used, 0))
