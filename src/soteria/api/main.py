"""Minimal FastAPI app: Plaid Link sandbox smoke test only.

No auth system — see soteria.plaid for the underlying Plaid calls and
persistence helpers.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from soteria.core.config import get_settings
from soteria.db.models.transactions import Transaction
from soteria.plaid.accounts import fetch_accounts
from soteria.plaid.bank_accounts import save_bank_accounts
from soteria.plaid.items import (
    get_decrypted_access_token,
    get_plaid_item,
    get_plaid_item_by_item_id,
    save_plaid_item,
)
from soteria.plaid.link import create_link_token, exchange_public_token
from soteria.plaid.services.sync_service import sync_item_transactions
from soteria.plaid.webhook_dedup import claim_webhook_event
from soteria.plaid.webhook_events import resolve_sync_event
from soteria.plaid.webhook_verification import is_webhook_authentic
from soteria.worker.tasks.plaid_sync import sync_plaid_item_transactions

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


class PlaidWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    webhook_type: str
    webhook_code: str
    item_id: str
    new_transactions: int | None = None


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
    result = sync_item_transactions(plaid_item)
    return SyncTransactionsResponse(
        added=[_transaction_summary(t) for t in result.added],
        modified=[_transaction_summary(t) for t in result.modified],
        removed_count=result.removed_count,
        next_cursor=result.next_cursor,
    )


@app.post("/plaid/webhook")
async def plaid_webhook(request: Request) -> dict[str, str]:
    body = await request.body()

    if get_settings().plaid_webhook_verification_enabled:
        signed_jwt = request.headers.get("Plaid-Verification")
        if not signed_jwt or not is_webhook_authentic(body, signed_jwt):
            raise HTTPException(status_code=401, detail="Webhook signature verification failed")

    try:
        payload = PlaidWebhookPayload.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="Malformed webhook payload") from exc

    plaid_item = get_plaid_item_by_item_id(payload.item_id)
    if plaid_item is None:
        raise HTTPException(status_code=404, detail="Unknown item_id")

    sync_event = resolve_sync_event(payload.webhook_code)
    if sync_event is None:
        print(f"No mapped action for webhook_code={payload.webhook_code}; ignoring")
        return {"status": "ignored"}

    if not claim_webhook_event(payload.item_id, payload.webhook_code):
        print(f"Duplicate delivery: webhook_code={payload.webhook_code} item {payload.item_id}")
        return {"status": "duplicate", "event": sync_event.value}

    print(f"webhook_code={payload.webhook_code} -> {sync_event.value} for item {payload.item_id}")
    sync_plaid_item_transactions.delay(str(plaid_item.id))
    return {"status": "enqueued", "event": sync_event.value}
