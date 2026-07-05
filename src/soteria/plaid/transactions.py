"""Persist Plaid /transactions/sync entries as transactions rows.

"added" inserts new rows, "modified" updates the existing row matched by
plaid_transaction_id, and "removed" soft-deletes via removed_at.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from plaid.model.removed_transaction import RemovedTransaction
from plaid.model.transaction import Transaction as PlaidTransaction
from sqlalchemy.orm import Session

from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.plaid_items import PlaidItem
from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal


def _category_string(category: list[str] | None) -> str | None:
    return ", ".join(category) if category else None


def _account_id_map(session: Session, plaid_item_id: uuid.UUID) -> dict[str, uuid.UUID]:
    bank_accounts = session.query(BankAccount).filter_by(plaid_item_id=plaid_item_id).all()
    return {bank_account.plaid_account_id: bank_account.id for bank_account in bank_accounts}


def _apply_fields(
    transaction: Transaction, txn: PlaidTransaction, *, user_id: uuid.UUID, account_id: uuid.UUID
) -> None:
    transaction.user_id = user_id
    transaction.account_id = account_id
    transaction.plaid_transaction_id = txn.transaction_id
    transaction.merchant_name = txn.merchant_name
    transaction.description = txn.name
    transaction.amount = Decimal(str(txn.amount))
    transaction.currency = txn.iso_currency_code or txn.unofficial_currency_code or "USD"
    transaction.transaction_date = txn.date
    transaction.authorized_date = txn.authorized_date
    transaction.pending = txn.pending
    transaction.category = _category_string(txn.category)
    transaction.payment_channel = txn.payment_channel
    transaction.location_json = txn.location.to_dict() if txn.location else None


def save_added_transactions(
    plaid_item: PlaidItem, added: list[PlaidTransaction]
) -> list[Transaction]:
    with SessionLocal() as session:
        account_id_by_plaid_account_id = _account_id_map(session, plaid_item.id)

        transactions = []
        for txn in added:
            account_id = account_id_by_plaid_account_id.get(txn.account_id)
            if account_id is None:
                print(f"Skipping txn {txn.transaction_id}: unknown account {txn.account_id}")
                continue
            transaction = Transaction()
            _apply_fields(transaction, txn, user_id=plaid_item.user_id, account_id=account_id)
            transactions.append(transaction)

        session.add_all(transactions)
        session.commit()
        for transaction in transactions:
            session.refresh(transaction)
        return transactions


def save_modified_transactions(
    plaid_item: PlaidItem, modified: list[PlaidTransaction]
) -> list[Transaction]:
    with SessionLocal() as session:
        account_id_by_plaid_account_id = _account_id_map(session, plaid_item.id)

        updated = []
        for txn in modified:
            transaction = (
                session.query(Transaction)
                .filter_by(plaid_transaction_id=txn.transaction_id)
                .one_or_none()
            )
            if transaction is None:
                print(f"Modified txn {txn.transaction_id} not found locally; skipping")
                continue
            account_id = account_id_by_plaid_account_id.get(txn.account_id)
            if account_id is None:
                print(f"Skipping txn {txn.transaction_id}: unknown account {txn.account_id}")
                continue
            _apply_fields(transaction, txn, user_id=plaid_item.user_id, account_id=account_id)
            updated.append(transaction)

        session.commit()
        for transaction in updated:
            session.refresh(transaction)
        return updated


def soft_delete_removed_transactions(removed: list[RemovedTransaction]) -> int:
    if not removed:
        return 0
    transaction_ids = [txn.transaction_id for txn in removed]
    with SessionLocal() as session:
        rows = (
            session.query(Transaction)
            .filter(Transaction.plaid_transaction_id.in_(transaction_ids))
            .all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.removed_at = now
        session.commit()
        return len(rows)
