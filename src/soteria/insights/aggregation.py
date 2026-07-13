"""Whole-user analytical queries powering insight generation.

Unlike analysis/transaction_history.py (which looks at a user's history to
score one transaction), every function here answers a question about the
user's entire transaction/subscription/account picture — monthly category
totals, merchant totals, average spend, weekly spending, largest expenses,
subscription costs, cash flow, account balances. Each takes an already-open
Session + user_id, same convention as fetch_scoring_inputs, and returns
plain data (dicts/lists/dataclasses) rather than ORM objects, since callers
use the results after the session that fetched them has closed.

Recomputed from scratch on every call — cheap at current volume, same
tradeoff transaction_history.py makes for the same reason.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from soteria.analysis.services.scoring import FRAUD_REASON_THRESHOLD
from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.merchant_profiles import MerchantProfile
from soteria.db.models.subscriptions import Subscription, SubscriptionStatus
from soteria.db.models.transaction_analysis import TransactionAnalysis
from soteria.db.models.transactions import Transaction
from soteria.insights.models.aggregates import (
    AccountBalanceRow,
    AnomalyClusterStats,
    CategoryMonthStat,
    InsightInputs,
    LargestExpenseRow,
    SubscriptionSnapshot,
)

# spending_above_normal reuses the same "this deviation is notable" cutoff
# process_transaction already uses for fraud_reason, just applied to
# anomaly_score instead of fraud_score.
ANOMALY_SCORE_THRESHOLD = FRAUD_REASON_THRESHOLD
ANOMALY_WINDOW_DAYS = 30


def shift_month(d: date, delta: int) -> date:
    """Return the first of the month `delta` months from `d` (negative = past)."""
    month_index = d.month - 1 + delta
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def monthly_category_totals(
    session: Session, user_id: uuid.UUID, *, months: int = 4, today: date | None = None
) -> dict[tuple[int, int, str], CategoryMonthStat]:
    today = today or date.today()
    window_start = shift_month(date(today.year, today.month, 1), -(months - 1))

    rows = (
        session.query(
            Transaction.transaction_date,
            Transaction.amount,
            TransactionAnalysis.normalized_category,
        )
        .join(TransactionAnalysis, TransactionAnalysis.transaction_id == Transaction.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.amount > 0,
            Transaction.transaction_date >= window_start,
            TransactionAnalysis.normalized_category.is_not(None),
        )
        .all()
    )

    totals: dict[tuple[int, int, str], Decimal] = defaultdict(lambda: Decimal("0"))
    counts: dict[tuple[int, int, str], int] = defaultdict(int)
    for transaction_date, amount, category in rows:
        key = (transaction_date.year, transaction_date.month, category)
        totals[key] += amount
        counts[key] += 1

    return {
        key: CategoryMonthStat(total=total, transaction_count=counts[key])
        for key, total in totals.items()
    }


def merchant_totals(session: Session, user_id: uuid.UUID, *, since: date) -> dict[str, Decimal]:
    rows = (
        session.query(TransactionAnalysis.normalized_merchant, Transaction.amount)
        .join(Transaction, Transaction.id == TransactionAnalysis.transaction_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.amount > 0,
            Transaction.transaction_date >= since,
            TransactionAnalysis.normalized_merchant.is_not(None),
        )
        .all()
    )
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for merchant, amount in rows:
        totals[merchant] += amount
    return dict(totals)


def category_merchant_totals(
    session: Session, user_id: uuid.UUID, *, since: date
) -> dict[tuple[str, str], Decimal]:
    """Keyed by (category, merchant) — spend within one category attributed
    to one merchant. Distinct from merchant_totals(), which is a merchant's
    share of *all* spend; this is what powers "y% of your Food spending was
    at Cafe A" rather than "y% of your overall spending was at Cafe A"."""
    rows = (
        session.query(
            TransactionAnalysis.normalized_category,
            TransactionAnalysis.normalized_merchant,
            Transaction.amount,
        )
        .join(Transaction, Transaction.id == TransactionAnalysis.transaction_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.amount > 0,
            Transaction.transaction_date >= since,
            TransactionAnalysis.normalized_category.is_not(None),
            TransactionAnalysis.normalized_merchant.is_not(None),
        )
        .all()
    )
    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for category, merchant, amount in rows:
        totals[(category, merchant)] += amount
    return dict(totals)


def average_spend(
    session: Session,
    user_id: uuid.UUID,
    *,
    category: str | None = None,
    months: int = 6,
    today: date | None = None,
) -> Decimal:
    """Mean monthly spend over the trailing `months` *completed* months (the
    current in-progress month is excluded, so a partial month never drags
    the baseline down)."""
    today = today or date.today()
    window_end = date(today.year, today.month, 1)
    window_start = shift_month(window_end, -months)

    query = session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.removed_at.is_(None),
        Transaction.amount > 0,
        Transaction.transaction_date >= window_start,
        Transaction.transaction_date < window_end,
    )
    if category is not None:
        query = query.join(
            TransactionAnalysis, TransactionAnalysis.transaction_id == Transaction.id
        ).filter(TransactionAnalysis.normalized_category == category)

    total = query.scalar() or Decimal("0")
    return total / months if months else Decimal("0")


def weekly_spending(
    session: Session, user_id: uuid.UUID, *, weeks: int = 12, today: date | None = None
) -> dict[date, Decimal]:
    """Net cash flow per week (outflow minus inflow), keyed by each week's
    Monday. Amounts already carry Plaid's sign convention (outflow positive,
    inflow negative), so summing directly yields net without a separate
    income query — this is what low_balance_forecast's burn rate uses."""
    today = today or date.today()
    window_start = today - timedelta(weeks=weeks)

    rows = (
        session.query(Transaction.transaction_date, Transaction.amount)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.transaction_date >= window_start,
        )
        .all()
    )
    totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for transaction_date, amount in rows:
        week_start = transaction_date - timedelta(days=transaction_date.weekday())
        totals[week_start] += amount
    return dict(totals)


def largest_expenses(
    session: Session, user_id: uuid.UUID, *, since: date, limit: int = 5
) -> list[LargestExpenseRow]:
    rows = (
        session.query(
            Transaction.id,
            Transaction.amount,
            Transaction.transaction_date,
            TransactionAnalysis.normalized_merchant,
            TransactionAnalysis.normalized_category,
        )
        .join(TransactionAnalysis, TransactionAnalysis.transaction_id == Transaction.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.amount > 0,
            Transaction.transaction_date >= since,
        )
        .order_by(Transaction.amount.desc())
        .limit(limit)
        .all()
    )
    return [
        LargestExpenseRow(
            transaction_id=row.id,
            merchant=row.normalized_merchant or "Unknown",
            category=row.normalized_category or "Other",
            amount=row.amount,
            year=row.transaction_date.year,
            month=row.transaction_date.month,
        )
        for row in rows
    ]


def subscription_costs(session: Session, user_id: uuid.UUID) -> list[SubscriptionSnapshot]:
    rows = (
        session.query(Subscription, MerchantProfile.category)
        .outerjoin(MerchantProfile, MerchantProfile.normalized_name == Subscription.normalized_name)
        .filter(Subscription.user_id == user_id, Subscription.status == SubscriptionStatus.ACTIVE)
        .all()
    )
    return [
        SubscriptionSnapshot(
            subscription_id=subscription.id,
            merchant_name=subscription.merchant_name,
            normalized_name=subscription.normalized_name,
            category=category,
            average_cost=subscription.average_cost,
            last_price_change_amount=subscription.last_price_change_amount,
            billing_cycle=subscription.billing_cycle,
            created_at=subscription.created_at.date(),
        )
        for subscription, category in rows
    ]


def monthly_cash_flow(
    session: Session, user_id: uuid.UUID, *, months: int = 4, today: date | None = None
) -> dict[tuple[int, int], tuple[Decimal, Decimal]]:
    """Per month: (income, spend), where income is a proxy — any inflow
    (paycheck, transfer, refund) counts, since there's no payroll classifier."""
    today = today or date.today()
    window_start = shift_month(date(today.year, today.month, 1), -(months - 1))

    rows = (
        session.query(Transaction.transaction_date, Transaction.amount)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.transaction_date >= window_start,
        )
        .all()
    )
    spend: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    income: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    for transaction_date, amount in rows:
        key = (transaction_date.year, transaction_date.month)
        if amount > 0:
            spend[key] += amount
        elif amount < 0:
            income[key] += -amount

    keys = set(spend) | set(income)
    return {key: (income[key], spend[key]) for key in keys}


def account_balances(session: Session, user_id: uuid.UUID) -> list[AccountBalanceRow]:
    rows = (
        session.query(BankAccount.id, BankAccount.current_balance)
        .filter(
            BankAccount.user_id == user_id,
            BankAccount.deleted_at.is_(None),
            BankAccount.current_balance.is_not(None),
        )
        .all()
    )
    return [
        AccountBalanceRow(account_id=row.id, current_balance=row.current_balance) for row in rows
    ]


def anomaly_cluster_stats(
    session: Session,
    user_id: uuid.UUID,
    *,
    window_days: int = ANOMALY_WINDOW_DAYS,
    today: date | None = None,
) -> AnomalyClusterStats:
    """The one aggregate that reads transaction_analysis.anomaly_score directly
    rather than raw transactions — that signal only exists there."""
    today = today or date.today()
    window_start = today - timedelta(days=window_days)

    rows = (
        session.query(Transaction.id)
        .join(TransactionAnalysis, TransactionAnalysis.transaction_id == Transaction.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.removed_at.is_(None),
            Transaction.transaction_date >= window_start,
            TransactionAnalysis.anomaly_score >= ANOMALY_SCORE_THRESHOLD,
        )
        .all()
    )
    transaction_ids = [row.id for row in rows]
    return AnomalyClusterStats(
        high_anomaly_count=len(transaction_ids), transaction_ids=transaction_ids
    )


def fetch_insight_inputs(
    session: Session, user_id: uuid.UUID, *, today: date | None = None
) -> InsightInputs:
    today = today or date.today()
    month_start = date(today.year, today.month, 1)

    expenses = largest_expenses(session, user_id, since=month_start)
    expense_categories = {expense.category for expense in expenses}
    average_spend_by_category = {
        category: average_spend(session, user_id, category=category, today=today)
        for category in expense_categories
    }

    return InsightInputs(
        today=today,
        monthly_category_totals=monthly_category_totals(session, user_id, today=today),
        average_spend_by_category=average_spend_by_category,
        merchant_totals_this_month=merchant_totals(session, user_id, since=month_start),
        category_merchant_totals_this_month=category_merchant_totals(
            session, user_id, since=month_start
        ),
        weekly_spending=weekly_spending(session, user_id, today=today),
        largest_expenses_this_month=expenses,
        subscriptions=subscription_costs(session, user_id),
        monthly_cash_flow=monthly_cash_flow(session, user_id, today=today),
        account_balances=account_balances(session, user_id),
        anomaly_cluster=anomaly_cluster_stats(session, user_id, today=today),
    )
