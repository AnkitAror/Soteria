"""Unit tests for heuristic financial scoring — pure functions, no DB."""

from datetime import date, timedelta
from decimal import Decimal

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.services.scoring import build_history_stats, compute_scores

TODAY = date(2026, 7, 6)


def _txn(amount: str, days_ago: int, merchant: str, category: str) -> TransactionFeatures:
    return TransactionFeatures(
        amount=Decimal(amount),
        transaction_date=TODAY - timedelta(days=days_ago),
        normalized_merchant=merchant,
        normalized_category=category,
    )


def _assert_scores_in_range(scores) -> None:  # type: ignore[no-untyped-def]
    assert Decimal("0") <= scores.anomaly_score <= Decimal("1")
    assert Decimal("0") <= scores.fraud_score <= Decimal("1")
    assert Decimal("0") <= scores.behavioral_score <= Decimal("1")
    assert Decimal("0") <= scores.smart_purchase_score <= Decimal("1")


def test_first_ever_transaction_has_no_baseline() -> None:
    current = _txn("50", 0, "New Cafe", "Food")
    history = build_history_stats(current, [], set())

    assert history.total_prior_transactions == 0
    assert history.confidence == Decimal("0")

    scores = compute_scores(current, history)
    _assert_scores_in_range(scores)
    assert scores.spending_deviation is None
    assert scores.category_monthly_average is None
    assert scores.merchant_frequency == Decimal("0.0000")


def test_normal_repeat_transaction_scores_low_anomaly() -> None:
    current = _txn("50", 0, "Cafe A", "Food")
    past = [
        _txn(str(a), d, "Cafe A", "Food")
        for a, d in [("48", 5), ("52", 10), ("49", 15), ("51", 20)]
    ]

    history = build_history_stats(current, past, set())
    scores = compute_scores(current, history)

    _assert_scores_in_range(scores)
    assert scores.spending_deviation is not None
    assert scores.anomaly_score < Decimal("0.2")
    assert scores.fraud_reason is None


def test_large_outlier_from_brand_new_merchant_triggers_fraud_reason() -> None:
    current = _txn("100", 0, "New Restaurant", "Food")
    # Five prior Food transactions from a *different* merchant, tight around $20 —
    # gives full confidence and a real stddev baseline for the category.
    past = [
        _txn(str(a), d, "Cafe A", "Food")
        for a, d in [("18", 5), ("19", 10), ("20", 15), ("21", 20), ("22", 25)]
    ]

    history = build_history_stats(current, past, set())
    assert history.confidence == Decimal("1.0")

    scores = compute_scores(current, history)
    _assert_scores_in_range(scores)
    assert scores.fraud_score >= Decimal("0.6")
    assert scores.fraud_reason is not None
    assert "Food" in scores.fraud_reason


def test_refund_short_circuits_to_neutral_scores() -> None:
    current = _txn("-75", 0, "Some Store", "Shopping")
    past = [_txn(str(a), d, "Some Store", "Shopping") for a, d in [("30", 5), ("40", 10)]]

    history = build_history_stats(current, past, set())
    scores = compute_scores(current, history)

    assert scores.anomaly_score == Decimal("0.0000")
    assert scores.fraud_score == Decimal("0.0000")
    assert scores.fraud_reason is None
    assert scores.behavioral_score == Decimal("0.5000")
    assert scores.smart_purchase_score == Decimal("0.5000")
    assert scores.spending_deviation is None


def test_high_same_day_velocity_raises_fraud_score() -> None:
    current = _txn("50", 0, "Cafe A", "Food")
    baseline_past = [_txn(str(a), d, "Cafe A", "Food") for a, d in [("48", 5), ("52", 10)]]
    high_velocity_past = baseline_past + [_txn("50", 0, "Cafe A", "Food") for _ in range(6)]

    baseline_scores = compute_scores(current, build_history_stats(current, baseline_past, set()))
    high_velocity_scores = compute_scores(
        current, build_history_stats(current, high_velocity_past, set())
    )

    assert high_velocity_scores.fraud_score > baseline_scores.fraud_score


def test_known_subscription_merchant_raises_smart_purchase_score() -> None:
    current = _txn("15.99", 0, "Streamflix", "Entertainment")
    past = [_txn("15.99", d, "Streamflix", "Entertainment") for d in (30, 60, 90)]

    not_subscription = compute_scores(current, build_history_stats(current, past, set()))
    is_subscription = compute_scores(current, build_history_stats(current, past, {"Streamflix"}))

    assert is_subscription.smart_purchase_score > not_subscription.smart_purchase_score
