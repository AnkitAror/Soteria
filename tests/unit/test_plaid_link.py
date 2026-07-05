"""Unit tests for the Plaid Link flow — no real network calls."""

from unittest.mock import MagicMock, patch

from soteria.plaid.link import create_link_token, exchange_public_token


def test_create_link_token_returns_token() -> None:
    fake_response = MagicMock(link_token="link-sandbox-fake")
    with patch("soteria.plaid.link.plaid_client") as mock_client:
        mock_client.link_token_create.return_value = fake_response
        assert create_link_token() == "link-sandbox-fake"


def test_exchange_public_token_returns_access_token_and_item_id() -> None:
    fake_response = MagicMock(access_token="access-sandbox-fake", item_id="item-fake")
    with patch("soteria.plaid.link.plaid_client") as mock_client:
        mock_client.item_public_token_exchange.return_value = fake_response
        access_token, item_id = exchange_public_token("public-sandbox-fake")
        assert access_token == "access-sandbox-fake"
        assert item_id == "item-fake"
