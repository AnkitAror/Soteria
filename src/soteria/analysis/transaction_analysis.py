"""Persist `transaction_analysis` rows — one per transaction, upserted on re-analysis.

Both functions take an open session rather than opening their own: they're
called back-to-back with other writes on the single-transaction critical
path (worker/tasks/process_transaction.py) and in a batch loop
(analysis/subscriptions.py::link_transactions_to_subscription) — sharing one
session there avoids a fresh connection-pool checkout per call. Committing
is the caller's responsibility.
"""

import uuid

from sqlalchemy.orm import Session

from soteria.analysis.models.scoring import ScoringResult
from soteria.db.models.transaction_analysis import TransactionAnalysis

ANALYSIS_VERSION = "v2"


def save_analysis(
    session: Session,
    transaction_id: uuid.UUID,
    *,
    normalized_merchant: str | None = None,
    normalized_category: str | None = None,
    subscription_id: uuid.UUID | None = None,
) -> TransactionAnalysis:
    analysis = (
        session.query(TransactionAnalysis).filter_by(transaction_id=transaction_id).one_or_none()
    )
    if analysis is None:
        analysis = TransactionAnalysis(
            transaction_id=transaction_id, analysis_version=ANALYSIS_VERSION
        )
        session.add(analysis)
    if normalized_merchant is not None:
        analysis.normalized_merchant = normalized_merchant
    if normalized_category is not None:
        analysis.normalized_category = normalized_category
    if subscription_id is not None:
        analysis.subscription_id = subscription_id
    analysis.analysis_version = ANALYSIS_VERSION
    return analysis


def save_scores(
    session: Session, transaction_id: uuid.UUID, scores: ScoringResult
) -> TransactionAnalysis:
    """Unlike save_analysis's optional-merge, scores are replaced atomically as a full
    set on every re-analysis — e.g. fraud_reason must be clearable to None if a
    re-score no longer crosses the reason threshold, which an optional merge can't do.
    """
    analysis = (
        session.query(TransactionAnalysis).filter_by(transaction_id=transaction_id).one_or_none()
    )
    if analysis is None:
        analysis = TransactionAnalysis(
            transaction_id=transaction_id, analysis_version=ANALYSIS_VERSION
        )
        session.add(analysis)
    analysis.anomaly_score = scores.anomaly_score
    analysis.fraud_score = scores.fraud_score
    analysis.fraud_reason = scores.fraud_reason
    analysis.behavioral_score = scores.behavioral_score
    analysis.smart_purchase_score = scores.smart_purchase_score
    analysis.merchant_frequency = scores.merchant_frequency
    analysis.category_monthly_average = scores.category_monthly_average
    analysis.spending_deviation = scores.spending_deviation
    analysis.analysis_version = ANALYSIS_VERSION
    return analysis
