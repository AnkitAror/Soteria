"""One-off connectivity check against Plaid Sandbox. Creates a link_token only;
no Link UI, no token exchange.

Usage: uv run python scripts/check_plaid_connection.py
"""

from soteria.plaid.link import create_link_token


def main() -> None:
    link_token = create_link_token()
    print("Connected successfully.")
    print(f"link_token: {link_token}")


if __name__ == "__main__":
    main()
