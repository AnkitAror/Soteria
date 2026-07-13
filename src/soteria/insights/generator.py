"""User-level insight generation — the module's main entry point.

The conceptual pivot of this whole package: every function up through
process_transaction takes a transaction_id and looks at one row.
generate_insights takes a user_id and looks at everything.
"""

import uuid
from decimal import Decimal

from soteria.db.models.insights import Insight
from soteria.db.session import SessionLocal
from soteria.insights.aggregation import fetch_insight_inputs, shift_month
from soteria.insights.models.aggregates import InsightDraft, InsightInputs
from soteria.insights.persistence import upsert_insight
from soteria.insights.services import rules

CATEGORY_TREND_MONTHS = 3
SAVINGS_TREND_MONTHS = 3


def generate_insights(user_id: uuid.UUID) -> list[Insight]:
    with SessionLocal() as session:
        inputs = fetch_insight_inputs(session, user_id)

    drafts: list[InsightDraft] = []
    drafts.extend(_spending_drafts(inputs))
    drafts.extend(_subscription_drafts(inputs))
    drafts.extend(_cash_flow_drafts(inputs))
    drafts.extend(_behavioral_drafts(inputs))

    return [upsert_insight(user_id, draft) for draft in drafts]


def _spending_drafts(inputs: InsightInputs) -> list[InsightDraft]:
    drafts: list[InsightDraft] = []
    categories = sorted({key[2] for key in inputs.monthly_category_totals})
    month_start = inputs.today.replace(day=1)
    current_month = (inputs.today.year, inputs.today.month)
    prior_month_date = shift_month(month_start, -1)
    prior_month = (prior_month_date.year, prior_month_date.month)

    for category in categories:
        current = inputs.monthly_category_totals.get((*current_month, category))
        prior = inputs.monthly_category_totals.get((*prior_month, category))
        if current is not None and prior is not None:
            increase = rules.category_spend_increase_rule(
                category,
                current.total,
                current.transaction_count,
                prior.total,
                prior.transaction_count,
            )
            if increase:
                drafts.append(increase)
            decrease = rules.category_spend_decrease_rule(
                category,
                current.total,
                current.transaction_count,
                prior.total,
                prior.transaction_count,
            )
            if decrease:
                drafts.append(decrease)

        trailing_months = [
            shift_month(month_start, -offset) for offset in range(CATEGORY_TREND_MONTHS, 0, -1)
        ]
        trailing_totals = [
            inputs.monthly_category_totals[(d.year, d.month, category)].total
            for d in trailing_months
            if (d.year, d.month, category) in inputs.monthly_category_totals
        ]
        if len(trailing_totals) == CATEGORY_TREND_MONTHS:
            trend = rules.category_spending_trend_rule(category, trailing_totals)
            if trend:
                drafts.append(trend)

    return drafts


def _subscription_drafts(inputs: InsightInputs) -> list[InsightDraft]:
    drafts: list[InsightDraft] = []
    by_category: dict[str, list] = {}

    for subscription in inputs.subscriptions:
        new_subscription = rules.new_subscription_detected_rule(
            subscription.subscription_id,
            subscription.merchant_name,
            subscription.created_at,
            today=inputs.today,
        )
        if new_subscription:
            drafts.append(new_subscription)

        if subscription.last_price_change_amount and subscription.last_price_change_amount > 0:
            previous_cost = subscription.average_cost - subscription.last_price_change_amount
            increase = rules.subscription_price_increase_rule(
                subscription.subscription_id,
                subscription.merchant_name,
                previous_cost,
                subscription.last_price_change_amount,
            )
            if increase:
                drafts.append(increase)

        if subscription.category:
            by_category.setdefault(subscription.category, []).append(subscription)

    for category, subscriptions in by_category.items():
        duplicate = rules.duplicate_subscriptions_rule(category, subscriptions)
        if duplicate:
            drafts.append(duplicate)

    return drafts


def _cash_flow_drafts(inputs: InsightInputs) -> list[InsightDraft]:
    drafts: list[InsightDraft] = []
    current_month = (inputs.today.year, inputs.today.month)
    income, spend = inputs.monthly_cash_flow.get(current_month, (Decimal("0"), Decimal("0")))
    exceeds = rules.spending_exceeds_income_rule(current_month[0], current_month[1], income, spend)
    if exceeds:
        drafts.append(exceeds)

    daily_burn_rate = _estimate_daily_burn_rate(inputs)
    for account in inputs.account_balances:
        forecast = rules.low_balance_forecast_rule(
            account.account_id, account.current_balance, daily_burn_rate
        )
        if forecast:
            drafts.append(forecast)

    completed_months = sorted(key for key in inputs.monthly_cash_flow if key != current_month)
    monthly_net = [
        inputs.monthly_cash_flow[key][0] - inputs.monthly_cash_flow[key][1]
        for key in completed_months
    ]
    if len(monthly_net) >= SAVINGS_TREND_MONTHS:
        trend = rules.savings_trend_rule(monthly_net[-SAVINGS_TREND_MONTHS:])
        if trend:
            drafts.append(trend)

    return drafts


def _estimate_daily_burn_rate(inputs: InsightInputs) -> Decimal:
    if not inputs.weekly_spending:
        return Decimal("0")
    total = sum(inputs.weekly_spending.values(), start=Decimal("0"))
    weeks = len(inputs.weekly_spending)
    return total / (weeks * 7)


def _behavioral_drafts(inputs: InsightInputs) -> list[InsightDraft]:
    drafts: list[InsightDraft] = []

    if inputs.largest_expenses_this_month:
        top = inputs.largest_expenses_this_month[0]
        category_average = inputs.average_spend_by_category.get(top.category)
        highlight = rules.largest_purchase_this_month_rule(
            top.transaction_id,
            top.merchant,
            top.category,
            top.amount,
            category_average,
            top.year,
            top.month,
        )
        if highlight:
            drafts.append(highlight)

    month_total = sum(inputs.merchant_totals_this_month.values(), start=Decimal("0"))
    for merchant, merchant_total in inputs.merchant_totals_this_month.items():
        concentration = rules.merchant_concentration_rule(merchant, merchant_total, month_total)
        if concentration:
            drafts.append(concentration)

    anomaly = rules.spending_above_normal_rule(
        inputs.anomaly_cluster.high_anomaly_count, inputs.anomaly_cluster.transaction_ids
    )
    if anomaly:
        drafts.append(anomaly)

    return drafts
