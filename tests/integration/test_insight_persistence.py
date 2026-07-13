"""Integration tests for upsert_insight's update/expire/replace logic.

This is the riskiest part of the insights design (see persistence.py's
docstring) and deserves direct coverage against a real database, not just an
end-to-end check through generate_insights().
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from soteria.db.models.insights import Insight
from soteria.db.session import SessionLocal
from soteria.insights.models.aggregates import InsightDraft
from soteria.insights.persistence import list_active_insights_for_user, upsert_insight


def _draft(
    value_signature: str,
    *,
    severity: str = "medium",
    identity_key: str = "category_spend_increase:Food",
) -> InsightDraft:
    return InsightDraft(
        type=identity_key.split(":")[0],
        title="Food spending increased",
        description="You spent 28% more on Food this month than last month.",
        severity=severity,
        confidence=Decimal("0.9167"),
        identity_key=identity_key,
        value_signature=value_signature,
        expires_in_days=14,
        metadata={"category": "Food"},
    )


def test_upsert_insight_inserts_when_no_active_match(test_user_id: uuid.UUID) -> None:
    insight = upsert_insight(test_user_id, _draft("medium:1.28"))

    assert insight.user_id == test_user_id
    assert insight.type == "category_spend_increase"
    assert insight.metadata_json is not None
    assert insight.metadata_json["identity_key"] == "category_spend_increase:Food"
    assert insight.metadata_json["value_signature"] == "medium:1.28"


def test_upsert_insight_updates_in_place_for_same_value_signature(test_user_id: uuid.UUID) -> None:
    first = upsert_insight(test_user_id, _draft("medium:1.28"))
    second = upsert_insight(test_user_id, _draft("medium:1.28"))

    assert second.id == first.id
    assert second.expires_at is not None
    assert first.expires_at is not None
    assert second.expires_at > first.expires_at

    with SessionLocal() as session:
        count = session.query(Insight).filter(Insight.user_id == test_user_id).count()
    assert count == 1


def test_upsert_insight_expires_old_and_replaces_for_different_value_signature(
    test_user_id: uuid.UUID,
) -> None:
    first = upsert_insight(test_user_id, _draft("medium:1.28"))
    second = upsert_insight(test_user_id, _draft("high:2.10"))

    assert second.id != first.id
    assert second.metadata_json is not None
    assert second.metadata_json["value_signature"] == "high:2.10"

    with SessionLocal() as session:
        refreshed_first = session.get(Insight, first.id)
        assert refreshed_first is not None
        assert refreshed_first.expires_at is not None
        assert refreshed_first.expires_at <= datetime.now(UTC)

        count = session.query(Insight).filter(Insight.user_id == test_user_id).count()
    assert count == 2


def test_upsert_insight_ignores_dismissed_insight_and_inserts_fresh(
    test_user_id: uuid.UUID,
) -> None:
    first = upsert_insight(test_user_id, _draft("medium:1.28"))

    with SessionLocal() as session:
        insight = session.get(Insight, first.id)
        assert insight is not None
        insight.dismissed_at = datetime.now(UTC)
        session.commit()

    second = upsert_insight(test_user_id, _draft("medium:1.28"))

    assert second.id != first.id


def test_list_active_insights_ranks_by_severity_not_recency(test_user_id: uuid.UUID) -> None:
    # Inserted in low-priority-first order, so a plain recency sort would put
    # the coffee bump ahead of the low-balance warning — ranking must not.
    coffee_bump = upsert_insight(
        test_user_id,
        _draft("medium:1.03", severity="medium", identity_key="category_spend_increase:Food"),
    )
    low_balance = upsert_insight(
        test_user_id,
        _draft("4", severity="high", identity_key="low_balance_forecast:acct-1"),
    )
    fyi = upsert_insight(
        test_user_id,
        _draft("detected", severity="info", identity_key="new_subscription:sub-1"),
    )

    ranked = list_active_insights_for_user(test_user_id)
    ranked_ids = [insight.id for insight in ranked]

    assert ranked_ids == [low_balance.id, coffee_bump.id, fyi.id]
