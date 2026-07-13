"""Pure data types for whole-user insight generation — not DB models.

Mirrors analysis/models/scoring.py's shape: frozen dataclasses only, no DB
access, so aggregation.py's queries and services/rules.py's heuristics stay
independently testable without a database.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

# Canonical severity vocabulary, most urgent first — every rule in
# services/rules.py assigns one of these. Order, not the string itself, is
# what ranking relies on (see severity_rank / list_active_insights_for_user),
# so this tuple is the single source of truth for "what outranks what."
SEVERITY_ORDER = ("high", "medium", "low", "info")


def severity_rank(severity: str) -> int:
    """Lower rank = higher priority. An unrecognized severity sorts last
    rather than raising, so a bad/future value degrades gracefully instead
    of breaking the whole ranked list."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return len(SEVERITY_ORDER)


@dataclass(frozen=True)
class CategoryMonthStat:
    total: Decimal
    transaction_count: int


@dataclass(frozen=True)
class SubscriptionSnapshot:
    subscription_id: UUID
    merchant_name: str
    normalized_name: str
    category: str | None
    average_cost: Decimal
    last_price_change_amount: Decimal | None
    billing_cycle: str
    created_at: date


@dataclass(frozen=True)
class LargestExpenseRow:
    transaction_id: UUID
    merchant: str
    category: str
    amount: Decimal
    year: int
    month: int


@dataclass(frozen=True)
class AccountBalanceRow:
    account_id: UUID
    current_balance: Decimal


@dataclass(frozen=True)
class AnomalyClusterStats:
    high_anomaly_count: int
    transaction_ids: list[UUID]


@dataclass(frozen=True)
class InsightInputs:
    """Bundles every aggregation.py query result for one user, fetched once per
    generate_insights() run so no query runs twice across the 12 rules."""

    today: date
    monthly_category_totals: dict[tuple[int, int, str], CategoryMonthStat]
    average_spend_by_category: dict[str, Decimal]
    merchant_totals_this_month: dict[str, Decimal]
    weekly_spending: dict[date, Decimal]
    largest_expenses_this_month: list[LargestExpenseRow]
    subscriptions: list[SubscriptionSnapshot]
    monthly_cash_flow: dict[tuple[int, int], tuple[Decimal, Decimal]]
    account_balances: list[AccountBalanceRow]
    anomaly_cluster: AnomalyClusterStats


@dataclass(frozen=True)
class InsightDraft:
    """Common output shape every rule in services/rules.py returns.

    identity_key names *what the insight is about* (stable across
    recomputation — a category, a subscription, an account, a month);
    value_signature is a short string capturing *the specific detected
    value*. persistence.upsert_insight uses the two together to decide
    whether to update an existing row in place, expire-and-replace it, or
    insert a fresh one.
    """

    type: str
    title: str
    description: str
    severity: str
    confidence: Decimal
    identity_key: str
    value_signature: str
    expires_in_days: int
    metadata: dict[str, Any]
