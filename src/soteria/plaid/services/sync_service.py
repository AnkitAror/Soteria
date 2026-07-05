"""Transaction sync service: given a Plaid Item, download all new transactions.

Orchestrates the existing Plaid sync + persistence building blocks. No
Celery, no scoring/analysis — those are separate concerns.
"""

from dataclasses import dataclass

from soteria.db.models.plaid_items import PlaidItem
from soteria.db.models.transactions import Transaction
from soteria.plaid.items import get_decrypted_access_token, update_sync_cursor
from soteria.plaid.transactions import (
    save_added_transactions,
    save_modified_transactions,
    soft_delete_removed_transactions,
)
from soteria.plaid.transactions_sync import sync_transactions


@dataclass
class TransactionSyncResult:
    added: list[Transaction]
    modified: list[Transaction]
    removed_count: int
    next_cursor: str


def sync_item_transactions(plaid_item: PlaidItem) -> TransactionSyncResult:
    access_token = get_decrypted_access_token(plaid_item)
    sync_result = sync_transactions(access_token, plaid_item.sync_cursor)
    added = save_added_transactions(plaid_item, sync_result.added)
    modified = save_modified_transactions(plaid_item, sync_result.modified)
    removed_count = soft_delete_removed_transactions(sync_result.removed)
    update_sync_cursor(plaid_item.id, sync_result.next_cursor)
    return TransactionSyncResult(
        added=added,
        modified=modified,
        removed_count=removed_count,
        next_cursor=sync_result.next_cursor,
    )
