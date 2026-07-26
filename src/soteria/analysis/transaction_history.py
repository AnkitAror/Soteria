"""Fetch a user's transaction history to feed the scoring pipeline.

Historical rows are re-normalized/re-categorized from raw `transactions`
columns here rather than joined from `transaction_analysis` — that avoids
staleness if some past row hasn't been enriched yet, or was enriched under
an older rule version.

Checks scoring_cache.py's Redis cache first; on a miss, runs the Postgres
query below (unchanged) and populates the cache for next time. See
scoring_cache.py's module docstring for the cache design and why
build_history_stats/compute_scores are untouched by this.
"""

from sqlalchemy.orm import Session

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.scoring_cache import get_cached_history, store_history
from soteria.analysis.services.categorization import categorize_transaction
from soteria.analysis.services.merchant_normalization import normalize_merchant
from soteria.db.models.transaction_analysis import TransactionAnalysis
from soteria.db.models.transactions import Transaction


def fetch_scoring_inputs(
    session: Session, transaction: Transaction
) -> tuple[list[TransactionFeatures], set[str]]:
    cached = get_cached_history(transaction.user_id, exclude_transaction_id=transaction.id)
    if cached is not None:
        past_features, subscription_merchants = cached
        # Cache entries accumulate in processing order, not chronological
        # order, so the as-of-date filter the Postgres query always applied
        # has to be re-applied here too -- this is required for scoring
        # correctness, not an optimization.
        return (
            [f for f in past_features if f.transaction_date <= transaction.transaction_date],
            subscription_merchants,
        )

    rows = (
        session.query(Transaction)
        .filter(
            Transaction.user_id == transaction.user_id,
            Transaction.id != transaction.id,
            Transaction.removed_at.is_(None),
            Transaction.transaction_date <= transaction.transaction_date,
        )
        .all()
    )

    features_by_id = [
        (
            row.id,
            TransactionFeatures(
                amount=row.amount,
                transaction_date=row.transaction_date,
                normalized_merchant=normalize_merchant(row.description),
                normalized_category=categorize_transaction(row.category, row.description),
            ),
        )
        for row in rows
    ]

    subscription_merchants = {
        row[0]
        for row in session.query(TransactionAnalysis.normalized_merchant)
        .join(Transaction, Transaction.id == TransactionAnalysis.transaction_id)
        .filter(
            Transaction.user_id == transaction.user_id,
            TransactionAnalysis.subscription_id.is_not(None),
            TransactionAnalysis.normalized_merchant.is_not(None),
        )
        .distinct()
        .all()
    }

    store_history(transaction.user_id, features_by_id, subscription_merchants)
    return [features for _, features in features_by_id], subscription_merchants
