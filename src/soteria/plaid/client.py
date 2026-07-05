"""Reusable Plaid API client — one instance per process, built at import time."""

import plaid
from plaid.api import plaid_api

from soteria.core.config import get_settings

_settings = get_settings()

_ENVIRONMENTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}

_configuration = plaid.Configuration(
    host=_ENVIRONMENTS[_settings.plaid_env],
    api_key={
        "clientId": _settings.plaid_client_id,
        "secret": _settings.plaid_secret,
    },
)

_api_client = plaid.ApiClient(_configuration)

plaid_client = plaid_api.PlaidApi(_api_client)
