"""Plaid Link flow: link_token creation and public_token exchange.

No DB writes here — see the PlaidItem model for the persistence layer,
added in a later pass.
"""

import uuid

from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products

from soteria.core.config import get_settings
from soteria.plaid.client import plaid_client

CLIENT_NAME = "Soteria (Sandbox)"


def create_link_token(user_id: uuid.UUID, access_token: str | None = None) -> str:
    """access_token=None creates a link_token for a brand-new Item. Passing an
    existing Item's access_token opens Link in "update mode" for relinking
    expired credentials — Plaid requires `products` to be omitted in that case.
    """
    extra_kwargs = {}
    webhook_url = get_settings().plaid_webhook_url
    if webhook_url:
        extra_kwargs["webhook"] = webhook_url

    if access_token is not None:
        request = LinkTokenCreateRequest(
            access_token=access_token,
            client_name=CLIENT_NAME,
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            **extra_kwargs,
        )
    else:
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name=CLIENT_NAME,
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            **extra_kwargs,
        )
    response = plaid_client.link_token_create(request)
    return str(response.link_token)


def exchange_public_token(public_token: str) -> tuple[str, str]:
    """Returns (access_token, item_id). Persistence is out of scope here."""
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = plaid_client.item_public_token_exchange(request)
    return str(response.access_token), str(response.item_id)
