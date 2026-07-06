"""Fetch a user's transaction history to feed the scoring pipeline.

Historical rows are re-normalized/re-categorized from raw `transactions`
columns here rather than joined from `transaction_analysis` — that avoids
staleness if some past row hasn't been enriched yet, or was enriched under
an older rule version. Cheap at current volume; a future optimization point
if it ever isn't.
"""

from sqlalchemy.orm import Session

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.services.categorization import categorize_transaction
from soteria.analysis.services.merchant_normalization import normalize_merchant
from soteria.db.models.transaction_analysis import TransactionAnalysis
from soteria.db.models.transactions import Transaction


def fetch_scoring_inputs(
    session: Session, transaction: Transaction
) -> tuple[list[TransactionFeatures], set[str]]:
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

    past_features = [
        TransactionFeatures(
            amount=row.amount,
            transaction_date=row.transaction_date,
            normalized_merchant=normalize_merchant(row.description),
            normalized_category=categorize_transaction(row.category, row.description),
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

    return past_features, subscription_merchants
