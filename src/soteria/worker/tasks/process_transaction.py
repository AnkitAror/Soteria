"""Celery task: process a single transaction asynchronously.

Takes a transaction_id, not the Transaction object itself — ORM objects
can't cross process boundaries, so the worker loads it fresh from the
database. Matches the same id-passing pattern as plaid.sync_plaid_item.
"""

import uuid

from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal
from soteria.worker.celery_app import app


@app.task(name="analysis.process_transaction")
def process_transaction(transaction_id: str) -> None:
    with SessionLocal() as session:
        transaction = session.get(Transaction, uuid.UUID(transaction_id))
        if transaction is None:
            print(f"process_transaction: no Transaction found for id={transaction_id}; skipping")
            return
        print(f"Loaded transaction {transaction.id}: {transaction.description}")
