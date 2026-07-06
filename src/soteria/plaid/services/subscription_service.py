"""Subscription detection: given a Plaid Item, detect recurring outflows and persist them.

Uses Plaid's own /transactions/recurring/get rather than building recurrence
detection ourselves.
"""

from soteria.analysis.subscriptions import link_transactions_to_subscription, save_subscription
from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.plaid_items import PlaidItem
from soteria.db.models.subscriptions import Subscription
from soteria.db.session import SessionLocal
from soteria.plaid.items import get_decrypted_access_token
from soteria.plaid.recurring import fetch_recurring_outflow_streams


def detect_subscriptions(plaid_item: PlaidItem) -> list[Subscription]:
    access_token = get_decrypted_access_token(plaid_item)

    with SessionLocal() as session:
        account_ids = [
            row[0]
            for row in session.query(BankAccount.plaid_account_id)
            .filter_by(plaid_item_id=plaid_item.id)
            .all()
        ]

    streams = fetch_recurring_outflow_streams(access_token, account_ids)

    subscriptions = []
    for stream in streams:
        subscription = save_subscription(plaid_item.user_id, stream)
        link_transactions_to_subscription(subscription.id, stream.transaction_ids)
        subscriptions.append(subscription)
    return subscriptions
