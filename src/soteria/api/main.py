"""Minimal FastAPI app: Plaid Link sandbox smoke test only.

No auth system — see soteria.plaid for the underlying Plaid calls and
persistence helpers.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from soteria.db.models.transactions import Transaction
from soteria.plaid.accounts import fetch_accounts
from soteria.plaid.bank_accounts import save_bank_accounts
from soteria.plaid.items import (
    get_decrypted_access_token,
    get_plaid_item,
    save_plaid_item,
    update_sync_cursor,
)
from soteria.plaid.link import create_link_token, exchange_public_token
from soteria.plaid.transactions import (
    save_added_transactions,
    save_modified_transactions,
    soft_delete_removed_transactions,
)
from soteria.plaid.transactions_sync import sync_transactions

app = FastAPI(title="Soteria Plaid Sandbox Test")

_STATIC_DIR = Path(__file__).parent / "static"


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    public_token: str
    institution_id: str
    institution_name: str


class ExchangeResponse(BaseModel):
    plaid_item_id: str
    item_id: str
    status: str


class AccountsRequest(BaseModel):
    plaid_item_id: str


class BankAccountSummary(BaseModel):
    id: str
    account_name: str
    account_type: str
    account_subtype: str | None
    current_balance: str | None
    available_balance: str | None
    currency: str


class AccountsResponse(BaseModel):
    accounts: list[BankAccountSummary]


class SyncTransactionsRequest(BaseModel):
    plaid_item_id: str


class TransactionSummary(BaseModel):
    id: str
    description: str
    merchant_name: str | None
    amount: str
    currency: str
    transaction_date: str
    pending: bool


class SyncTransactionsResponse(BaseModel):
    added: list[TransactionSummary]
    modified: list[TransactionSummary]
    removed_count: int
    next_cursor: str


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/api/plaid/link-token")
def link_token() -> LinkTokenResponse:
    return LinkTokenResponse(link_token=create_link_token())


@app.post("/api/plaid/exchange")
def exchange(payload: ExchangeRequest) -> ExchangeResponse:
    access_token, item_id = exchange_public_token(payload.public_token)
    plaid_item = save_plaid_item(
        item_id=item_id,
        access_token=access_token,
        institution_id=payload.institution_id,
        institution_name=payload.institution_name,
    )
    return ExchangeResponse(
        plaid_item_id=str(plaid_item.id),
        item_id=plaid_item.plaid_item_id,
        status=plaid_item.status.value,
    )


@app.post("/api/plaid/accounts")
def accounts(payload: AccountsRequest) -> AccountsResponse:
    plaid_item = get_plaid_item(payload.plaid_item_id)
    access_token = get_decrypted_access_token(plaid_item)
    fetched_accounts = fetch_accounts(access_token)
    bank_accounts = save_bank_accounts(plaid_item, fetched_accounts)
    return AccountsResponse(
        accounts=[
            BankAccountSummary(
                id=str(bank_account.id),
                account_name=bank_account.account_name,
                account_type=bank_account.account_type,
                account_subtype=bank_account.account_subtype,
                current_balance=str(bank_account.current_balance)
                if bank_account.current_balance is not None
                else None,
                available_balance=str(bank_account.available_balance)
                if bank_account.available_balance is not None
                else None,
                currency=bank_account.currency,
            )
            for bank_account in bank_accounts
        ]
    )


def _transaction_summary(transaction: Transaction) -> TransactionSummary:
    return TransactionSummary(
        id=str(transaction.id),
        description=transaction.description,
        merchant_name=transaction.merchant_name,
        amount=str(transaction.amount),
        currency=transaction.currency,
        transaction_date=transaction.transaction_date.isoformat(),
        pending=transaction.pending,
    )


@app.post("/api/plaid/transactions/sync")
def transactions_sync(payload: SyncTransactionsRequest) -> SyncTransactionsResponse:
    plaid_item = get_plaid_item(payload.plaid_item_id)
    access_token = get_decrypted_access_token(plaid_item)
    sync_result = sync_transactions(access_token, plaid_item.sync_cursor)
    added_transactions = save_added_transactions(plaid_item, sync_result.added)
    modified_transactions = save_modified_transactions(plaid_item, sync_result.modified)
    removed_count = soft_delete_removed_transactions(sync_result.removed)
    update_sync_cursor(plaid_item.id, sync_result.next_cursor)
    return SyncTransactionsResponse(
        added=[_transaction_summary(t) for t in added_transactions],
        modified=[_transaction_summary(t) for t in modified_transactions],
        removed_count=removed_count,
        next_cursor=sync_result.next_cursor,
    )
