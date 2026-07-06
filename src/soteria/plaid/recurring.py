"""Fetch recurring transaction streams for a Plaid Item via /transactions/recurring/get.

Only outflow streams are returned — subscriptions are recurring money
leaving the account, not recurring income (inflow streams). No DB writes
here.
"""

from plaid.model.transaction_stream import TransactionStream
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest

from soteria.plaid.client import plaid_client


def fetch_recurring_outflow_streams(
    access_token: str, account_ids: list[str]
) -> list[TransactionStream]:
    request = TransactionsRecurringGetRequest(access_token=access_token, account_ids=account_ids)
    response = plaid_client.transactions_recurring_get(request)
    return list(response.outflow_streams)
