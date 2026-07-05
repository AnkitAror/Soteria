"""Persist fetched Plaid accounts to the database as bank_accounts rows."""

from decimal import Decimal

from plaid.model.account_base import AccountBase

from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.plaid_items import PlaidItem
from soteria.db.session import SessionLocal


def _to_decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def save_bank_accounts(plaid_item: PlaidItem, accounts: list[AccountBase]) -> list[BankAccount]:
    with SessionLocal() as session:
        bank_accounts = [
            BankAccount(
                user_id=plaid_item.user_id,
                plaid_item_id=plaid_item.id,
                plaid_account_id=account.account_id,
                institution_name=plaid_item.institution_name,
                account_name=account.name,
                account_type=str(account.type),
                account_subtype=str(account.subtype) if account.subtype else None,
                current_balance=_to_decimal(account.balances.current),
                available_balance=_to_decimal(account.balances.available),
                currency=account.balances.iso_currency_code
                or account.balances.unofficial_currency_code
                or "USD",
            )
            for account in accounts
        ]
        session.add_all(bank_accounts)
        session.commit()
        for bank_account in bank_accounts:
            session.refresh(bank_account)
        return bank_accounts
