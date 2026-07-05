"""Fetch account data for a Plaid Item. No DB writes here."""

from plaid.model.account_base import AccountBase
from plaid.model.accounts_get_request import AccountsGetRequest

from soteria.plaid.client import plaid_client


def fetch_accounts(access_token: str) -> list[AccountBase]:
    request = AccountsGetRequest(access_token=access_token)
    response = plaid_client.accounts_get(request)
    return list(response.accounts)
