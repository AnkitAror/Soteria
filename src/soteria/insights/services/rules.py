"""Heuristic insight rules — the swappable "model" behind the insights.type catalog.

Pure functions only; no DB access, no session, no live clock reads (today/now
are always passed in). Same shape as analysis/services/scoring.py's
compute_scores(): when a rule's heuristic needs to get smarter, only its body
changes — generator.py's call sites stay identical. Every rule sees one
category/merchant/subscription/account/period at a time; generator.py is
responsible for looping.
"""

import uuid
from datetime import date
from decimal import Decimal
from itertools import pairwise

from soteria.insights.models.aggregates import InsightDraft, SubscriptionSnapshot

QUANT = Decimal("0.0001")

CATEGORY_NOISE_FLOOR = Decimal("20")
CATEGORY_INCREASE_RATIO = Decimal("1.2")
CATEGORY_INCREASE_HIGH_RATIO = Decimal("1.5")
CATEGORY_DECREASE_RATIO = Decimal("0.8")
CATEGORY_CONFIDENCE_TXN_FLOOR = Decimal("12")
CATEGORY_TREND_MONTHS = 3

NEW_SUBSCRIPTION_WINDOW_DAYS = 3
SUBSCRIPTION_PRICE_INCREASE_MIN_AMOUNT = Decimal("1")
SUBSCRIPTION_PRICE_INCREASE_MIN_PCT = Decimal("0.05")
SUBSCRIPTION_PRICE_INCREASE_HIGH_PCT = Decimal("0.20")

LOW_BALANCE_FORECAST_DEFAULT_THRESHOLD_DAYS = 14

LARGEST_PURCHASE_MIN_RATIO = Decimal("1.5")
MERCHANT_CONCENTRATION_THRESHOLD = Decimal("0.25")
MERCHANT_CONCENTRATION_MONTH_FLOOR = Decimal("100")
ANOMALY_CLUSTER_MIN_COUNT = 2


def _category_confidence(count_a: int, count_b: int) -> Decimal:
    """More transactions backing the comparison -> more confident it's a real
    pattern, not one outlier purchase. Same shape as HistoryStats.confidence
    in analysis/services/scoring.py, floored on transaction count."""
    return min(Decimal(count_a + count_b) / CATEGORY_CONFIDENCE_TXN_FLOOR, Decimal("1")).quantize(
        QUANT
    )


# --- Spending -----------------------------------------------------------


def category_spend_increase_rule(
    category: str,
    current_month_total: Decimal,
    current_month_txn_count: int,
    prior_month_total: Decimal,
    prior_month_txn_count: int,
) -> InsightDraft | None:
    if prior_month_total < CATEGORY_NOISE_FLOOR:
        return None
    ratio = (current_month_total / prior_month_total).quantize(QUANT)
    if ratio <= CATEGORY_INCREASE_RATIO:
        return None
    severity = "high" if ratio >= CATEGORY_INCREASE_HIGH_RATIO else "medium"
    percent = ((ratio - 1) * 100).quantize(Decimal("1"))
    return InsightDraft(
        type="category_spend_increase",
        title=f"{category} spending increased",
        description=f"You spent {percent}% more on {category} this month than last month.",
        severity=severity,
        confidence=_category_confidence(current_month_txn_count, prior_month_txn_count),
        identity_key=f"category_spend_increase:{category}",
        value_signature=f"{severity}:{ratio}",
        expires_in_days=14,
        metadata={
            "category": category,
            "current_month_total": str(current_month_total),
            "prior_month_total": str(prior_month_total),
            "ratio": str(ratio),
        },
    )


def category_spend_decrease_rule(
    category: str,
    current_month_total: Decimal,
    current_month_txn_count: int,
    prior_month_total: Decimal,
    prior_month_txn_count: int,
) -> InsightDraft | None:
    if prior_month_total < CATEGORY_NOISE_FLOOR:
        return None
    ratio = (current_month_total / prior_month_total).quantize(QUANT)
    if ratio >= CATEGORY_DECREASE_RATIO:
        return None
    percent = ((1 - ratio) * 100).quantize(Decimal("1"))
    return InsightDraft(
        type="category_spend_decrease",
        title=f"{category} spending decreased",
        description=f"You spent {percent}% less on {category} this month than last month.",
        severity="info",
        confidence=_category_confidence(current_month_txn_count, prior_month_txn_count),
        identity_key=f"category_spend_decrease:{category}",
        value_signature=str(ratio),
        expires_in_days=14,
        metadata={
            "category": category,
            "current_month_total": str(current_month_total),
            "prior_month_total": str(prior_month_total),
            "ratio": str(ratio),
        },
    )


def category_spending_trend_rule(
    category: str, trailing_totals: list[Decimal]
) -> InsightDraft | None:
    if len(trailing_totals) < CATEGORY_TREND_MONTHS:
        return None
    if sum(trailing_totals) / len(trailing_totals) < CATEGORY_NOISE_FLOOR:
        return None
    rising = all(a < b for a, b in pairwise(trailing_totals))
    falling = all(a > b for a, b in pairwise(trailing_totals))
    if not rising and not falling:
        return None
    direction = "rising" if rising else "falling"
    verb = "risen" if rising else "fallen"
    baseline = trailing_totals[0] if trailing_totals[0] > 0 else Decimal("1")
    swing = abs(trailing_totals[-1] - trailing_totals[0]) / baseline
    confidence = min(swing, Decimal("1")).quantize(QUANT)
    return InsightDraft(
        type="category_spending_trend",
        title=f"{category} spending is {direction}",
        description=(
            f"Your {category} spending has {verb} for {len(trailing_totals)} months in a row."
        ),
        severity="low",
        confidence=confidence,
        identity_key=f"category_spending_trend:{category}",
        value_signature=direction,
        expires_in_days=30,
        metadata={"category": category, "trailing_totals": [str(t) for t in trailing_totals]},
    )


# --- Subscription ---------------------------------------------------------


def new_subscription_detected_rule(
    subscription_id: uuid.UUID, merchant_name: str, created_at: date, *, today: date
) -> InsightDraft | None:
    if (today - created_at).days > NEW_SUBSCRIPTION_WINDOW_DAYS:
        return None
    return InsightDraft(
        type="new_subscription_detected",
        title="New subscription detected",
        description=f"We noticed a new recurring charge from {merchant_name}.",
        severity="info",
        confidence=Decimal("0.9000"),
        identity_key=f"new_subscription:{subscription_id}",
        value_signature="detected",
        expires_in_days=14,
        metadata={"subscription_id": str(subscription_id), "merchant_name": merchant_name},
    )


def subscription_price_increase_rule(
    subscription_id: uuid.UUID,
    merchant_name: str,
    previous_cost: Decimal,
    change_amount: Decimal,
) -> InsightDraft | None:
    if change_amount <= 0:
        return None
    pct = (change_amount / previous_cost).quantize(QUANT) if previous_cost > 0 else None
    if change_amount < SUBSCRIPTION_PRICE_INCREASE_MIN_AMOUNT and (
        pct is None or pct < SUBSCRIPTION_PRICE_INCREASE_MIN_PCT
    ):
        return None
    is_high = pct is not None and pct >= SUBSCRIPTION_PRICE_INCREASE_HIGH_PCT
    severity = "high" if is_high else "medium"
    new_cost = previous_cost + change_amount
    return InsightDraft(
        type="subscription_price_increase",
        title=f"{merchant_name} price increased",
        description=f"{merchant_name} went up from ${previous_cost:.2f} to ${new_cost:.2f}.",
        severity=severity,
        confidence=Decimal("0.9500"),
        identity_key=f"subscription_price_increase:{subscription_id}",
        value_signature=str(change_amount),
        expires_in_days=30,
        metadata={
            "subscription_id": str(subscription_id),
            "merchant_name": merchant_name,
            "previous_cost": str(previous_cost),
            "new_cost": str(new_cost),
            "change_amount": str(change_amount),
        },
    )


def duplicate_subscriptions_rule(
    category: str, subscriptions: list[SubscriptionSnapshot]
) -> InsightDraft | None:
    if len(subscriptions) < 2:
        return None
    names = sorted(s.merchant_name for s in subscriptions)
    ids = sorted(str(s.subscription_id) for s in subscriptions)
    return InsightDraft(
        type="duplicate_subscriptions",
        title=f"Possible overlapping {category} subscriptions",
        description=(
            f"You have {len(subscriptions)} active {category} subscriptions: {', '.join(names)}."
        ),
        severity="low",
        confidence=Decimal("0.6000"),
        identity_key=f"duplicate_subscriptions:{category}",
        value_signature=str(ids),
        expires_in_days=30,
        metadata={"category": category, "subscription_ids": ids, "merchant_names": names},
    )


# --- Cash Flow --------------------------------------------------------------


def spending_exceeds_income_rule(
    year: int, month: int, income: Decimal, spend: Decimal
) -> InsightDraft | None:
    if spend <= income:
        return None
    deficit = spend - income
    return InsightDraft(
        type="spending_exceeds_income",
        title="Spending exceeded income this month",
        description=f"You spent ${spend:.2f} against ${income:.2f} in income this month.",
        severity="medium",
        confidence=Decimal("0.8000"),
        identity_key=f"spending_exceeds_income:{year}-{month:02d}",
        value_signature=f"{deficit:.0f}",
        expires_in_days=30,
        metadata={"year": year, "month": month, "income": str(income), "spend": str(spend)},
    )


def low_balance_forecast_rule(
    account_id: uuid.UUID,
    current_balance: Decimal,
    daily_burn_rate: Decimal,
    *,
    threshold_days: int = LOW_BALANCE_FORECAST_DEFAULT_THRESHOLD_DAYS,
) -> InsightDraft | None:
    if daily_burn_rate <= 0 or current_balance <= 0:
        return None
    projected_days = int(current_balance / daily_burn_rate)
    if projected_days > threshold_days:
        return None
    return InsightDraft(
        type="low_balance_forecast",
        title="Balance may run low soon",
        description=(
            f"At your current spending pace, this account could run out in about "
            f"{projected_days} day(s)."
        ),
        severity="high",
        confidence=Decimal("0.7500"),
        identity_key=f"low_balance_forecast:{account_id}",
        value_signature=str(projected_days),
        expires_in_days=7,
        metadata={
            "account_id": str(account_id),
            "current_balance": str(current_balance),
            "projected_days": projected_days,
        },
    )


def savings_trend_rule(monthly_net: list[Decimal]) -> InsightDraft | None:
    if len(monthly_net) < 3:
        return None
    declining = all(a > b for a, b in pairwise(monthly_net))
    improving = all(a < b for a, b in pairwise(monthly_net))
    if not declining and not improving:
        return None
    direction = "declining" if declining else "improving"
    severity = "medium" if declining else "info"
    return InsightDraft(
        type="savings_trend",
        title=f"Your savings are {direction}",
        description=(
            f"Your monthly net cash flow has been {direction} over the last "
            f"{len(monthly_net)} months."
        ),
        severity=severity,
        confidence=Decimal("0.7000"),
        identity_key="savings_trend",
        value_signature=direction,
        expires_in_days=30,
        metadata={"monthly_net": [str(n) for n in monthly_net]},
    )


# --- Behavioral --------------------------------------------------------------


def largest_purchase_this_month_rule(
    transaction_id: uuid.UUID,
    merchant: str,
    category: str,
    amount: Decimal,
    category_average: Decimal | None,
    year: int,
    month: int,
) -> InsightDraft | None:
    if category_average is None or category_average <= 0:
        return None
    if amount < LARGEST_PURCHASE_MIN_RATIO * category_average:
        return None
    return InsightDraft(
        type="largest_purchase_this_month",
        title="Largest purchase this month",
        description=f"Your biggest purchase this month was ${amount:.2f} at {merchant}.",
        severity="info",
        confidence=Decimal("0.9000"),
        identity_key=f"largest_purchase_this_month:{year}-{month:02d}",
        value_signature=str(transaction_id),
        expires_in_days=30,
        metadata={
            "transaction_id": str(transaction_id),
            "merchant": merchant,
            "category": category,
            "amount": str(amount),
        },
    )


def merchant_concentration_rule(
    merchant: str, merchant_total: Decimal, month_total: Decimal
) -> InsightDraft | None:
    if month_total < MERCHANT_CONCENTRATION_MONTH_FLOOR:
        return None
    share = (merchant_total / month_total).quantize(QUANT)
    if share < MERCHANT_CONCENTRATION_THRESHOLD:
        return None
    return InsightDraft(
        type="merchant_concentration",
        title=f"Most of your spending went to {merchant}",
        description=f"{share:.0%} of your spending this month was at {merchant}.",
        severity="low",
        confidence=Decimal("0.8000"),
        identity_key=f"merchant_concentration:{merchant}",
        value_signature=str(share),
        expires_in_days=14,
        metadata={
            "merchant": merchant,
            "merchant_total": str(merchant_total),
            "month_total": str(month_total),
            "share": str(share),
        },
    )


def spending_above_normal_rule(
    high_anomaly_count: int, transaction_ids: list[uuid.UUID]
) -> InsightDraft | None:
    if high_anomaly_count < ANOMALY_CLUSTER_MIN_COUNT:
        return None
    return InsightDraft(
        type="spending_above_normal",
        title="Unusual spending activity",
        description=(
            f"{high_anomaly_count} recent transactions looked unusual compared to your "
            f"normal spending."
        ),
        severity="medium",
        confidence=Decimal("0.7000"),
        identity_key="spending_above_normal:30d",
        value_signature=str(sorted(str(t) for t in transaction_ids)),
        expires_in_days=7,
        metadata={
            "high_anomaly_count": high_anomaly_count,
            "transaction_ids": [str(t) for t in transaction_ids],
        },
    )
