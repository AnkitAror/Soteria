"""Celery task: process a single transaction asynchronously.

Takes a transaction_id, not the Transaction object itself — ORM objects
can't cross process boundaries, so the worker loads it fresh from the
database. Matches the same id-passing pattern as plaid.sync_plaid_item.
"""

import uuid

from soteria.analysis.services.categorization import categorize_transaction
from soteria.analysis.services.merchant_normalization import normalize_merchant
from soteria.analysis.transaction_analysis import save_analysis
from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal
from soteria.worker.celery_app import app


@app.task(name="analysis.process_transaction")
def process_transaction(transaction_id: str) -> None:
    txn_uuid = uuid.UUID(transaction_id)

    with SessionLocal() as session:
        transaction = session.get(Transaction, txn_uuid)
        if transaction is None:
            print(f"process_transaction: no Transaction found for id={transaction_id}; skipping")
            return
        description = transaction.description
        plaid_category = transaction.category

    normalized_merchant = normalize_merchant(description)
    normalized_category = categorize_transaction(plaid_category, description)
    save_analysis(
        txn_uuid,
        normalized_merchant=normalized_merchant,
        normalized_category=normalized_category,
    )
    print(
        f"Enriched transaction {transaction_id}: "
        f"normalized_merchant={normalized_merchant} normalized_category={normalized_category}"
    )
