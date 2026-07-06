"""Heuristic financial scoring — the swappable "model" behind transaction_analysis's score columns.

Pure functions only; no DB access. When these heuristics get replaced by
something smarter (statistical model, ML), only the bodies of
build_history_stats/compute_scores need to change — process_transaction's
call site stays identical.
"""

import statistics
from decimal import Decimal

from soteria.analysis.models.scoring import HistoryStats, ScoringResult, TransactionFeatures

MERCHANT_FREQUENCY_WINDOW_DAYS = 90
CATEGORY_LOOKBACK_DAYS = 180
CONFIDENCE_FLOOR_COUNT = 5
Z_SCORE_CAP = Decimal("3.0")
FRAUD_REASON_THRESHOLD = Decimal("0.6")
QUANT = Decimal("0.0001")

CATEGORY_NECESSITY: dict[str, Decimal] = {
    "Utilities": Decimal("0.9"),
    "Food": Decimal("0.6"),
    "Travel": Decimal("0.5"),
    "Shopping": Decimal("0.4"),
    "Entertainment": Decimal("0.3"),
    "Other": Decimal("0.5"),
}


def _clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("1")) -> Decimal:
    return max(low, min(high, value))


def build_history_stats(
    current: TransactionFeatures,
    past: list[TransactionFeatures],
    subscription_merchants: set[str],
) -> HistoryStats:
    current_date = current.transaction_date
    merchant = current.normalized_merchant
    category = current.normalized_category

    outflow_past = [t for t in past if t.amount > 0]
    same_day_count = sum(1 for t in past if t.transaction_date == current_date)

    merchant_past = [t for t in outflow_past if t.normalized_merchant == merchant]
    merchant_all_time_count = len(merchant_past)
    merchant_recent_count_90d = sum(
        1
        for t in merchant_past
        if (current_date - t.transaction_date).days <= MERCHANT_FREQUENCY_WINDOW_DAYS
    )

    category_past = [t for t in outflow_past if t.normalized_category == category]
    category_recent = [
        t
        for t in category_past
        if (current_date - t.transaction_date).days <= CATEGORY_LOOKBACK_DAYS
    ]
    category_prior_count_180d = len(category_recent)

    if category_recent:
        amounts = [t.amount for t in category_recent]
        amounts_total = sum(amounts, start=Decimal("0"))
        category_mean_amount = amounts_total / len(amounts)
        category_stddev_amount = statistics.stdev(amounts) if len(amounts) >= 2 else None
        distinct_months = max(
            len({(t.transaction_date.year, t.transaction_date.month) for t in category_recent}), 1
        )
        category_monthly_average = amounts_total / distinct_months
    else:
        category_mean_amount = None
        category_stddev_amount = None
        category_monthly_average = None

    total_prior_transactions = len(past)
    confidence = min(
        Decimal(total_prior_transactions) / Decimal(CONFIDENCE_FLOOR_COUNT), Decimal("1.0")
    )

    return HistoryStats(
        total_prior_transactions=total_prior_transactions,
        same_day_count=same_day_count,
        merchant_all_time_count=merchant_all_time_count,
        merchant_recent_count_90d=merchant_recent_count_90d,
        category_prior_count_180d=category_prior_count_180d,
        category_mean_amount=category_mean_amount,
        category_stddev_amount=category_stddev_amount,
        category_monthly_average=category_monthly_average,
        is_known_subscription_merchant=merchant in subscription_merchants,
        confidence=confidence,
    )


def _build_fraud_reason(
    fraud_score: Decimal,
    category: str,
    large_outlier: Decimal,
    new_merchant_component: Decimal,
    velocity_component: Decimal,
    amount: Decimal,
    category_mean_amount: Decimal | None,
    same_day_count: int,
) -> str | None:
    if fraud_score < FRAUD_REASON_THRESHOLD:
        return None

    if (
        large_outlier >= new_merchant_component
        and large_outlier >= velocity_component
        and category_mean_amount
    ):
        if category_mean_amount > 0:
            multiple = amount / category_mean_amount
            return (
                f"Amount is {multiple:.1f}x the typical spend in {category} "
                f"(${category_mean_amount:.2f} avg)."
            )
        return f"Amount is unusually high for {category}."
    if new_merchant_component >= velocity_component:
        return "First-time transaction with this merchant combined with an above-average amount."
    return f"Unusually high transaction volume today ({same_day_count} transactions)."


def compute_scores(features: TransactionFeatures, history: HistoryStats) -> ScoringResult:
    amount = features.amount
    category = features.normalized_category

    merchant_frequency = Decimal(history.merchant_recent_count_90d).quantize(QUANT)
    category_monthly_average = (
        history.category_monthly_average.quantize(QUANT)
        if history.category_monthly_average is not None
        else None
    )

    if amount <= 0:
        # Refund/credit — scoring an inflow the same way as a spend doesn't
        # make sense; merchant/category stats still describe the merchant,
        # so they're still returned.
        return ScoringResult(
            anomaly_score=Decimal("0.0000"),
            fraud_score=Decimal("0.0000"),
            fraud_reason=None,
            behavioral_score=Decimal("0.5000"),
            smart_purchase_score=Decimal("0.5000"),
            merchant_frequency=merchant_frequency,
            category_monthly_average=category_monthly_average,
            spending_deviation=None,
        )

    if history.category_mean_amount is not None:
        if history.category_stddev_amount and history.category_stddev_amount > 0:
            spending_deviation = (
                amount - history.category_mean_amount
            ) / history.category_stddev_amount
        else:
            denom = max(history.category_mean_amount, Decimal("1.00"))
            spending_deviation = (amount - history.category_mean_amount) / denom
    else:
        spending_deviation = None

    amount_component = (
        Decimal("0")
        if spending_deviation is None
        else min(abs(spending_deviation) / Z_SCORE_CAP, Decimal("1"))
    )
    amount_typicality = (
        Decimal("0.5") if spending_deviation is None else (Decimal("1") - amount_component)
    )
    merchant_novelty = Decimal("1") if history.merchant_all_time_count == 0 else Decimal("0")
    category_novelty = Decimal("1") if history.category_prior_count_180d == 0 else Decimal("0")
    damping = Decimal("0.4") + Decimal("0.6") * history.confidence

    anomaly_score = _clamp(
        damping
        * (
            Decimal("0.60") * amount_component
            + Decimal("0.25") * merchant_novelty
            + Decimal("0.15") * category_novelty
        )
    )

    large_outlier = (
        Decimal("0")
        if spending_deviation is None
        else min(max(spending_deviation, Decimal("0")) / Z_SCORE_CAP, Decimal("1"))
    )
    if (
        history.merchant_all_time_count == 0
        and history.category_mean_amount is not None
        and amount > 2 * history.category_mean_amount
    ):
        new_merchant_component = Decimal("1.0")
    elif history.merchant_all_time_count == 0 and history.category_mean_amount is None:
        new_merchant_component = Decimal("0.4")
    else:
        new_merchant_component = Decimal("0.0")
    velocity_component = min(
        max(Decimal(history.same_day_count - 3), Decimal("0")) / Decimal("5"), Decimal("1")
    )

    fraud_score = _clamp(
        damping
        * (
            Decimal("0.5") * large_outlier
            + Decimal("0.3") * new_merchant_component
            + Decimal("0.2") * velocity_component
        )
    )

    fraud_reason = _build_fraud_reason(
        fraud_score,
        category,
        large_outlier,
        new_merchant_component,
        velocity_component,
        amount,
        history.category_mean_amount,
        history.same_day_count,
    )

    merchant_familiarity = min(
        Decimal(history.merchant_recent_count_90d) / Decimal("5"), Decimal("1")
    )
    category_familiarity = min(
        Decimal(history.category_prior_count_180d) / Decimal("10"), Decimal("1")
    )
    behavioral_score = _clamp(
        Decimal("0.4") * merchant_familiarity
        + Decimal("0.3") * category_familiarity
        + Decimal("0.3") * amount_typicality
    )

    necessity_weight = CATEGORY_NECESSITY.get(category, Decimal("0.5"))
    recurring_bonus = Decimal("1") if history.is_known_subscription_merchant else Decimal("0")
    smart_purchase_score = _clamp(
        Decimal("0.5") * necessity_weight
        + Decimal("0.3") * amount_typicality
        + Decimal("0.2") * recurring_bonus
    )

    return ScoringResult(
        anomaly_score=anomaly_score.quantize(QUANT),
        fraud_score=fraud_score.quantize(QUANT),
        fraud_reason=fraud_reason,
        behavioral_score=behavioral_score.quantize(QUANT),
        smart_purchase_score=smart_purchase_score.quantize(QUANT),
        merchant_frequency=merchant_frequency,
        category_monthly_average=category_monthly_average,
        spending_deviation=spending_deviation.quantize(QUANT)
        if spending_deviation is not None
        else None,
    )
