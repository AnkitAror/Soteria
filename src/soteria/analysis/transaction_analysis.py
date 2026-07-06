"""Persist `transaction_analysis` rows — one per transaction, upserted on re-analysis."""

import uuid

from soteria.db.models.transaction_analysis import TransactionAnalysis
from soteria.db.session import SessionLocal

ANALYSIS_VERSION = "v1"


def save_analysis(
    transaction_id: uuid.UUID,
    *,
    normalized_merchant: str | None = None,
    normalized_category: str | None = None,
    subscription_id: uuid.UUID | None = None,
) -> TransactionAnalysis:
    with SessionLocal() as session:
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
        session.commit()
        session.refresh(analysis)
        return analysis
