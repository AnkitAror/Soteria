"""Integration test: generate_insights() end to end against a real database,
including the update-in-place vs expire-and-replace behavior verified through
the public entry point (not just at the persistence-unit level).

Uses a subscription price change as the trigger — unlike the spending/cash
flow rules, a Subscription row needs no transactions/bank_accounts to exist,
keeping this test's setup minimal.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from soteria.db.models.insights import Insight
from soteria.db.models.subscriptions import Subscription, SubscriptionStatus
from soteria.db.session import SessionLocal
from soteria.insights.generator import generate_insights

MERCHANT_NAME = "Streamflix"
NORMALIZED_NAME = "streamflix"


def _create_subscription(
    user_id: uuid.UUID, *, average_cost: Decimal, last_price_change_amount: Decimal
) -> None:
    with SessionLocal() as session:
        subscription = Subscription(
            user_id=user_id,
            merchant_name=MERCHANT_NAME,
            normalized_name=NORMALIZED_NAME,
            average_cost=average_cost,
            currency="USD",
            billing_cycle="monthly",
            status=SubscriptionStatus.ACTIVE,
            last_price_change_amount=last_price_change_amount,
        )
        session.add(subscription)
        session.commit()


def test_generate_insights_updates_in_place_for_unchanged_subscription_price(
    test_user_id: uuid.UUID,
) -> None:
    _create_subscription(
        test_user_id, average_cost=Decimal("17.99"), last_price_change_amount=Decimal("2.00")
    )

    first = generate_insights(test_user_id)
    second = generate_insights(test_user_id)

    first_price_insight = next(i for i in first if i.type == "subscription_price_increase")
    second_price_insight = next(i for i in second if i.type == "subscription_price_increase")

    assert second_price_insight.id == first_price_insight.id
    assert first_price_insight.expires_at is not None
    assert second_price_insight.expires_at is not None
    assert second_price_insight.expires_at > first_price_insight.expires_at

    with SessionLocal() as session:
        count = (
            session.query(Insight)
            .filter(
                Insight.user_id == test_user_id,
                Insight.type == "subscription_price_increase",
            )
            .count()
        )
    assert count == 1


def test_generate_insights_replaces_insight_on_new_price_change(test_user_id: uuid.UUID) -> None:
    _create_subscription(
        test_user_id, average_cost=Decimal("17.99"), last_price_change_amount=Decimal("2.00")
    )
    first = generate_insights(test_user_id)
    first_price_insight = next(i for i in first if i.type == "subscription_price_increase")

    with SessionLocal() as session:
        subscription = (
            session.query(Subscription)
            .filter(
                Subscription.user_id == test_user_id,
                Subscription.normalized_name == NORMALIZED_NAME,
            )
            .one()
        )
        subscription.average_cost = Decimal("20.99")
        subscription.last_price_change_amount = Decimal("3.00")
        session.commit()

    second = generate_insights(test_user_id)
    second_price_insight = next(i for i in second if i.type == "subscription_price_increase")

    assert second_price_insight.id != first_price_insight.id
    assert second_price_insight.metadata_json is not None
    assert second_price_insight.metadata_json["value_signature"] == "3.00"

    with SessionLocal() as session:
        refreshed_first = session.get(Insight, first_price_insight.id)
        assert refreshed_first is not None
        assert refreshed_first.expires_at is not None
        assert refreshed_first.expires_at <= datetime.now(UTC)
