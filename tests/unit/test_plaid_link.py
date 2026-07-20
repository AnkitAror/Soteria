"""Unit tests for the Plaid Link flow — no real network calls."""

import uuid
from unittest.mock import MagicMock, patch

from soteria.plaid.link import create_link_token, exchange_public_token


def test_create_link_token_returns_token() -> None:
    fake_response = MagicMock(link_token="link-sandbox-fake")
    with patch("soteria.plaid.link.plaid_client") as mock_client:
        mock_client.link_token_create.return_value = fake_response
        assert create_link_token(uuid.uuid4()) == "link-sandbox-fake"


def test_create_link_token_update_mode_omits_products() -> None:
    fake_response = MagicMock(link_token="link-sandbox-update-fake")
    with patch("soteria.plaid.link.plaid_client") as mock_client:
        mock_client.link_token_create.return_value = fake_response
        token = create_link_token(uuid.uuid4(), access_token="access-sandbox-fake")
        assert token == "link-sandbox-update-fake"
        request = mock_client.link_token_create.call_args[0][0]
        assert request.access_token == "access-sandbox-fake"
        assert "products" not in request.to_dict()


def test_exchange_public_token_returns_access_token_and_item_id() -> None:
    fake_response = MagicMock(access_token="access-sandbox-fake", item_id="item-fake")
    with patch("soteria.plaid.link.plaid_client") as mock_client:
        mock_client.item_public_token_exchange.return_value = fake_response
        access_token, item_id = exchange_public_token("public-sandbox-fake")
        assert access_token == "access-sandbox-fake"
        assert item_id == "item-fake"
