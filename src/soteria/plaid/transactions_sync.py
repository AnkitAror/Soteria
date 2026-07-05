"""Fetch transaction deltas for a Plaid Item via /transactions/sync. No DB writes here."""

from dataclasses import dataclass, field

from plaid.model.removed_transaction import RemovedTransaction
from plaid.model.transaction import Transaction as PlaidTransaction
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from soteria.plaid.client import plaid_client


@dataclass
class SyncResult:
    added: list[PlaidTransaction] = field(default_factory=list)
    modified: list[PlaidTransaction] = field(default_factory=list)
    removed: list[RemovedTransaction] = field(default_factory=list)
    next_cursor: str = ""


def sync_transactions(access_token: str, cursor: str | None) -> SyncResult:
    """Pages through /transactions/sync until has_more is false."""
    result = SyncResult()
    has_more = True
    while has_more:
        request = (
            TransactionsSyncRequest(access_token=access_token, cursor=cursor)
            if cursor
            else TransactionsSyncRequest(access_token=access_token)
        )
        response = plaid_client.transactions_sync(request)
        result.added.extend(response.added)
        result.modified.extend(response.modified)
        result.removed.extend(response.removed)
        cursor = response.next_cursor
        has_more = response.has_more
    result.next_cursor = cursor or ""
    return result
