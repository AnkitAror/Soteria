"""Data types for heuristic financial scoring — not DB models."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class TransactionFeatures:
    amount: Decimal  # Plaid sign convention: >0 = money out, <=0 = refund/credit
    transaction_date: date
    normalized_merchant: str
    normalized_category: str


@dataclass(frozen=True)
class HistoryStats:
    total_prior_transactions: int
    same_day_count: int
    merchant_all_time_count: int
    merchant_recent_count_90d: int
    category_prior_count_180d: int
    category_mean_amount: Decimal | None
    category_stddev_amount: Decimal | None
    category_monthly_average: Decimal | None
    is_known_subscription_merchant: bool
    confidence: Decimal


@dataclass(frozen=True)
class ScoringResult:
    anomaly_score: Decimal
    fraud_score: Decimal
    fraud_reason: str | None
    behavioral_score: Decimal
    smart_purchase_score: Decimal
    merchant_frequency: Decimal
    category_monthly_average: Decimal | None
    spending_deviation: Decimal | None
