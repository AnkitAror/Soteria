"""Unit tests for heuristic insight rules — pure functions, no DB."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from soteria.insights.models.aggregates import SubscriptionSnapshot, severity_rank
from soteria.insights.services import rules

TODAY = date(2026, 7, 6)


def _assert_confidence_in_range(draft) -> None:  # type: ignore[no-untyped-def]
    assert Decimal("0") <= draft.confidence <= Decimal("1")


# --- category_spend_increase_rule / category_spend_decrease_rule -----------


def test_category_spend_increase_fires_above_threshold() -> None:
    draft = rules.category_spend_increase_rule("Food", Decimal("400.00"), 6, Decimal("312.50"), 5)

    assert draft is not None
    assert draft.type == "category_spend_increase"
    assert draft.title == "Food spending increased"
    assert draft.description == "You spent 28% more on Food this month than last month."
    assert draft.severity == "medium"
    assert draft.confidence == Decimal("0.9167")
    assert draft.identity_key == "category_spend_increase:Food"
    assert draft.value_signature == "medium:1.2800"
    assert draft.category == "Food"
    _assert_confidence_in_range(draft)


def test_category_spend_increase_severity_escalates_to_high() -> None:
    draft = rules.category_spend_increase_rule("Food", Decimal("700.00"), 6, Decimal("312.50"), 5)

    assert draft is not None
    assert draft.severity == "high"


def test_category_spend_increase_returns_none_below_threshold() -> None:
    draft = rules.category_spend_increase_rule("Food", Decimal("340.00"), 6, Decimal("312.50"), 5)

    assert draft is None


def test_category_spend_increase_returns_none_below_noise_floor() -> None:
    draft = rules.category_spend_increase_rule("Food", Decimal("15.00"), 2, Decimal("5.00"), 1)

    assert draft is None


def test_category_spend_decrease_fires_below_threshold() -> None:
    draft = rules.category_spend_decrease_rule(
        "Shopping", Decimal("100.00"), 3, Decimal("300.00"), 4
    )

    assert draft is not None
    assert draft.type == "category_spend_decrease"
    assert draft.severity == "info"
    assert draft.identity_key == "category_spend_decrease:Shopping"


def test_category_spend_decrease_returns_none_above_threshold() -> None:
    draft = rules.category_spend_decrease_rule(
        "Shopping", Decimal("280.00"), 3, Decimal("300.00"), 4
    )

    assert draft is None


def test_category_spend_increase_and_decrease_have_different_identity_keys() -> None:
    increase = rules.category_spend_increase_rule(
        "Food", Decimal("400.00"), 6, Decimal("312.50"), 5
    )
    decrease = rules.category_spend_decrease_rule(
        "Food", Decimal("100.00"), 3, Decimal("312.50"), 5
    )

    assert increase is not None
    assert decrease is not None
    assert increase.identity_key != decrease.identity_key


# --- category_spending_trend_rule -------------------------------------------


def test_category_spending_trend_fires_on_rising_totals() -> None:
    draft = rules.category_spending_trend_rule(
        "Food", [Decimal("100"), Decimal("150"), Decimal("220")]
    )

    assert draft is not None
    assert draft.value_signature == "rising"
    assert draft.identity_key == "category_spending_trend:Food"


def test_category_spending_trend_fires_on_falling_totals() -> None:
    draft = rules.category_spending_trend_rule(
        "Food", [Decimal("220"), Decimal("150"), Decimal("100")]
    )

    assert draft is not None
    assert draft.value_signature == "falling"


def test_category_spending_trend_returns_none_without_enough_months() -> None:
    draft = rules.category_spending_trend_rule("Food", [Decimal("100"), Decimal("150")])

    assert draft is None


def test_category_spending_trend_returns_none_when_not_monotonic() -> None:
    draft = rules.category_spending_trend_rule(
        "Food", [Decimal("100"), Decimal("150"), Decimal("120")]
    )

    assert draft is None


def test_category_spending_trend_returns_none_below_noise_floor() -> None:
    draft = rules.category_spending_trend_rule("Food", [Decimal("1"), Decimal("2"), Decimal("3")])

    assert draft is None


# --- new_subscription_detected_rule -----------------------------------------


def test_new_subscription_detected_fires_within_window() -> None:
    subscription_id = uuid.uuid4()
    draft = rules.new_subscription_detected_rule(
        subscription_id, "Streamflix", TODAY - timedelta(days=1), today=TODAY
    )

    assert draft is not None
    assert draft.identity_key == f"new_subscription:{subscription_id}"
    assert draft.value_signature == "detected"


def test_new_subscription_detected_returns_none_after_window() -> None:
    subscription_id = uuid.uuid4()
    draft = rules.new_subscription_detected_rule(
        subscription_id, "Streamflix", TODAY - timedelta(days=30), today=TODAY
    )

    assert draft is None


def test_new_subscription_detected_defaults_category_to_none() -> None:
    draft = rules.new_subscription_detected_rule(
        uuid.uuid4(), "Streamflix", TODAY - timedelta(days=1), today=TODAY
    )

    assert draft is not None
    assert draft.category is None


def test_new_subscription_detected_carries_category_when_provided() -> None:
    draft = rules.new_subscription_detected_rule(
        uuid.uuid4(), "Streamflix", TODAY - timedelta(days=1), today=TODAY, category="Entertainment"
    )

    assert draft is not None
    assert draft.category == "Entertainment"


# --- subscription_price_increase_rule ---------------------------------------


def test_subscription_price_increase_fires_above_threshold() -> None:
    subscription_id = uuid.uuid4()
    draft = rules.subscription_price_increase_rule(
        subscription_id, "Streamflix", Decimal("15.99"), Decimal("2.00")
    )

    assert draft is not None
    assert draft.severity == "medium"
    assert draft.identity_key == f"subscription_price_increase:{subscription_id}"
    assert draft.value_signature == "2.00"
    assert draft.category is None


def test_subscription_price_increase_carries_category_when_provided() -> None:
    draft = rules.subscription_price_increase_rule(
        uuid.uuid4(), "Streamflix", Decimal("15.99"), Decimal("2.00"), category="Entertainment"
    )

    assert draft is not None
    assert draft.category == "Entertainment"


def test_subscription_price_increase_severity_escalates_to_high() -> None:
    subscription_id = uuid.uuid4()
    draft = rules.subscription_price_increase_rule(
        subscription_id, "Streamflix", Decimal("10.00"), Decimal("5.00")
    )

    assert draft is not None
    assert draft.severity == "high"


def test_subscription_price_increase_returns_none_for_decrease() -> None:
    draft = rules.subscription_price_increase_rule(
        uuid.uuid4(), "Streamflix", Decimal("15.99"), Decimal("-2.00")
    )

    assert draft is None


def test_subscription_price_increase_returns_none_below_threshold() -> None:
    draft = rules.subscription_price_increase_rule(
        uuid.uuid4(), "Streamflix", Decimal("100.00"), Decimal("0.50")
    )

    assert draft is None


def test_subscription_price_increase_different_amounts_share_identity_but_differ_in_value() -> None:
    subscription_id = uuid.uuid4()
    first = rules.subscription_price_increase_rule(
        subscription_id, "Streamflix", Decimal("15.99"), Decimal("2.00")
    )
    second = rules.subscription_price_increase_rule(
        subscription_id, "Streamflix", Decimal("17.99"), Decimal("3.00")
    )

    assert first is not None
    assert second is not None
    assert first.identity_key == second.identity_key
    assert first.value_signature != second.value_signature


# --- duplicate_subscriptions_rule -------------------------------------------


def _subscription(merchant_name: str, category: str = "Entertainment") -> SubscriptionSnapshot:
    return SubscriptionSnapshot(
        subscription_id=uuid.uuid4(),
        merchant_name=merchant_name,
        normalized_name=merchant_name.lower(),
        category=category,
        average_cost=Decimal("9.99"),
        last_price_change_amount=None,
        billing_cycle="monthly",
        created_at=TODAY - timedelta(days=100),
    )


def test_duplicate_subscriptions_fires_with_two_or_more() -> None:
    subs = [_subscription("Streamflix"), _subscription("Tunestream")]
    draft = rules.duplicate_subscriptions_rule("Entertainment", subs)

    assert draft is not None
    assert draft.identity_key == "duplicate_subscriptions:Entertainment"
    assert draft.category == "Entertainment"


def test_duplicate_subscriptions_returns_none_with_one() -> None:
    draft = rules.duplicate_subscriptions_rule("Entertainment", [_subscription("Streamflix")])

    assert draft is None


# --- spending_exceeds_income_rule -------------------------------------------


def test_spending_exceeds_income_fires_on_deficit() -> None:
    draft = rules.spending_exceeds_income_rule(2026, 7, Decimal("2000"), Decimal("2500"))

    assert draft is not None
    assert draft.identity_key == "spending_exceeds_income:2026-07"
    assert draft.category is None  # account/cash-flow-level, not one category


def test_spending_exceeds_income_returns_none_when_within_income() -> None:
    draft = rules.spending_exceeds_income_rule(2026, 7, Decimal("2000"), Decimal("1500"))

    assert draft is None


# --- low_balance_forecast_rule -----------------------------------------------


def test_low_balance_forecast_fires_within_threshold() -> None:
    account_id = uuid.uuid4()
    draft = rules.low_balance_forecast_rule(account_id, Decimal("500"), Decimal("100"))

    assert draft is not None
    assert draft.identity_key == f"low_balance_forecast:{account_id}"
    assert draft.value_signature == "5"
    assert draft.category is None


def test_low_balance_forecast_returns_none_when_projection_beyond_threshold() -> None:
    draft = rules.low_balance_forecast_rule(uuid.uuid4(), Decimal("5000"), Decimal("10"))

    assert draft is None


def test_low_balance_forecast_returns_none_without_positive_burn_rate() -> None:
    draft = rules.low_balance_forecast_rule(uuid.uuid4(), Decimal("500"), Decimal("0"))

    assert draft is None


# --- savings_trend_rule -------------------------------------------------------


def test_savings_trend_fires_on_declining_net() -> None:
    draft = rules.savings_trend_rule([Decimal("500"), Decimal("300"), Decimal("100")])

    assert draft is not None
    assert draft.value_signature == "declining"
    assert draft.severity == "medium"


def test_savings_trend_fires_on_improving_net() -> None:
    draft = rules.savings_trend_rule([Decimal("100"), Decimal("300"), Decimal("500")])

    assert draft is not None
    assert draft.value_signature == "improving"
    assert draft.severity == "info"


def test_savings_trend_returns_none_without_enough_months() -> None:
    draft = rules.savings_trend_rule([Decimal("500"), Decimal("300")])

    assert draft is None


# --- largest_purchase_this_month_rule -----------------------------------------


def test_largest_purchase_fires_above_baseline() -> None:
    transaction_id = uuid.uuid4()
    draft = rules.largest_purchase_this_month_rule(
        transaction_id, "Best Buy", "Shopping", Decimal("900"), Decimal("300"), 2026, 7
    )

    assert draft is not None
    assert draft.identity_key == "largest_purchase_this_month:2026-07"
    assert draft.value_signature == str(transaction_id)
    assert draft.category == "Shopping"


def test_largest_purchase_returns_none_below_baseline() -> None:
    draft = rules.largest_purchase_this_month_rule(
        uuid.uuid4(), "Best Buy", "Shopping", Decimal("350"), Decimal("300"), 2026, 7
    )

    assert draft is None


def test_largest_purchase_returns_none_without_baseline() -> None:
    draft = rules.largest_purchase_this_month_rule(
        uuid.uuid4(), "Best Buy", "Shopping", Decimal("900"), None, 2026, 7
    )

    assert draft is None


# --- merchant_concentration_rule ----------------------------------------------


def test_merchant_concentration_fires_above_threshold() -> None:
    draft = rules.merchant_concentration_rule("Amazon", Decimal("300"), Decimal("1000"))

    assert draft is not None
    assert draft.identity_key == "merchant_concentration:Amazon"
    assert draft.category is None  # overall concentration isn't about one category


def test_merchant_concentration_returns_none_below_threshold() -> None:
    draft = rules.merchant_concentration_rule("Amazon", Decimal("100"), Decimal("1000"))

    assert draft is None


def test_merchant_concentration_returns_none_below_month_floor() -> None:
    draft = rules.merchant_concentration_rule("Amazon", Decimal("30"), Decimal("50"))

    assert draft is None


# --- category_merchant_concentration_rule -------------------------------------


def test_category_merchant_concentration_fires_above_threshold() -> None:
    draft = rules.category_merchant_concentration_rule(
        "Food", "Cafe A", Decimal("290"), Decimal("400")
    )

    assert draft is not None
    assert draft.type == "category_merchant_concentration"
    assert draft.title == "Most of your Food spending went to Cafe A"
    assert draft.description == "72% of your Food spending this month was at Cafe A."
    assert draft.identity_key == "category_merchant_concentration:Food:Cafe A"
    assert draft.category == "Food"


def test_category_merchant_concentration_returns_none_below_threshold() -> None:
    draft = rules.category_merchant_concentration_rule(
        "Food", "Cafe A", Decimal("50"), Decimal("400")
    )

    assert draft is None


def test_category_merchant_concentration_returns_none_below_category_noise_floor() -> None:
    draft = rules.category_merchant_concentration_rule(
        "Food", "Cafe A", Decimal("15"), Decimal("18")
    )

    assert draft is None


def test_category_merchant_concentration_differs_from_overall_merchant_concentration() -> None:
    # Same merchant, same raw dollar amount ($290) — but a much bigger share
    # of the Food category (72%) than of total monthly spend (29%). The two
    # rules must answer different questions, not just alias each other.
    within_category = rules.category_merchant_concentration_rule(
        "Food", "Cafe A", Decimal("290"), Decimal("400")
    )
    overall = rules.merchant_concentration_rule("Cafe A", Decimal("290"), Decimal("1000"))

    assert within_category is not None
    assert overall is not None
    assert within_category.value_signature != overall.value_signature
    assert within_category.category == "Food"
    assert overall.category is None


# --- spending_above_normal_rule -----------------------------------------------


def test_spending_above_normal_fires_at_min_count() -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]
    draft = rules.spending_above_normal_rule(2, ids)

    assert draft is not None
    assert draft.identity_key == "spending_above_normal:30d"


def test_spending_above_normal_returns_none_below_min_count() -> None:
    draft = rules.spending_above_normal_rule(1, [uuid.uuid4()])

    assert draft is None


# --- severity_rank -------------------------------------------------------


def test_severity_rank_orders_high_above_medium_above_low_above_info() -> None:
    assert severity_rank("high") < severity_rank("medium")
    assert severity_rank("medium") < severity_rank("low")
    assert severity_rank("low") < severity_rank("info")


def test_severity_rank_sorts_low_balance_forecast_above_coffee_spike() -> None:
    low_balance = rules.low_balance_forecast_rule(uuid.uuid4(), Decimal("100"), Decimal("30"))
    coffee_spike = rules.category_spend_increase_rule(
        "Food", Decimal("103.00"), 5, Decimal("100.00"), 5
    )

    assert low_balance is not None
    assert coffee_spike is None  # a real +3% doesn't even clear the fire threshold

    coffee_spike_forced = rules.category_spend_increase_rule(
        "Food", Decimal("125.00"), 5, Decimal("100.00"), 5
    )
    assert coffee_spike_forced is not None
    assert severity_rank(low_balance.severity) < severity_rank(coffee_spike_forced.severity)


def test_severity_rank_returns_last_place_for_unknown_severity() -> None:
    assert severity_rank("unknown") > severity_rank("info")
