"""Celery task: process a single transaction asynchronously.

Takes a transaction_id, not the Transaction object itself — ORM objects
can't cross process boundaries, so the worker loads it fresh from the
database. Matches the same id-passing pattern as plaid.sync_plaid_item.
"""

import uuid

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.services.categorization import categorize_transaction
from soteria.analysis.services.merchant_normalization import normalize_merchant
from soteria.analysis.services.scoring import build_history_stats, compute_scores
from soteria.analysis.subscriptions import find_active_subscription
from soteria.analysis.transaction_analysis import save_analysis, save_scores
from soteria.analysis.transaction_history import fetch_scoring_inputs
from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal
from soteria.worker.celery_app import app


@app.task(
    name="analysis.process_transaction",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def process_transaction(transaction_id: str) -> None:
    txn_uuid = uuid.UUID(transaction_id)

    # One session for the whole task rather than one per DB call (fetch,
    # subscription lookup, history, save_analysis, save_scores each used to
    # open their own) -- fewer connection-pool checkouts per transaction,
    # which is both faster and gentler on Supabase's pooler under load.
    with SessionLocal() as session:
        transaction = session.get(Transaction, txn_uuid)
        if transaction is None:
            print(f"process_transaction: no Transaction found for id={transaction_id}; skipping")
            return

        normalized_merchant = normalize_merchant(transaction.description)
        normalized_category = categorize_transaction(transaction.category, transaction.description)
        subscription_id = find_active_subscription(
            session, transaction.user_id, normalized_merchant
        )

        current_features = TransactionFeatures(
            amount=transaction.amount,
            transaction_date=transaction.transaction_date,
            normalized_merchant=normalized_merchant,
            normalized_category=normalized_category,
        )
        past_features, subscription_merchants = fetch_scoring_inputs(session, transaction)

        history = build_history_stats(current_features, past_features, subscription_merchants)
        scores = compute_scores(current_features, history)

        save_analysis(
            session,
            txn_uuid,
            normalized_merchant=normalized_merchant,
            normalized_category=normalized_category,
            subscription_id=subscription_id,
        )
        save_scores(session, txn_uuid, scores)
        session.commit()

    print(
        f"Enriched transaction {transaction_id}: normalized_merchant={normalized_merchant} "
        f"normalized_category={normalized_category} anomaly={scores.anomaly_score} "
        f"fraud={scores.fraud_score} behavioral={scores.behavioral_score} "
        f"smart_purchase={scores.smart_purchase_score}"
    )
