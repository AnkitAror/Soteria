"""Persist recurring outflow streams as `subscriptions` rows and link transactions to them.

Get-or-create is keyed on (user_id, normalized_name) — the same merchant
normalizer used for transaction enrichment, so "Spotify AB", "SPOTIFY USA",
etc. all resolve to one subscription row.
"""

import uuid
from decimal import Decimal

from plaid.model.transaction_stream import TransactionStream
from sqlalchemy.orm import Session

from soteria.analysis.scoring_cache import invalidate_history
from soteria.analysis.services.merchant_normalization import normalize_merchant
from soteria.analysis.transaction_analysis import save_analysis
from soteria.db.models.subscriptions import Subscription, SubscriptionStatus
from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal


def save_subscription(user_id: uuid.UUID, stream: TransactionStream) -> Subscription:
    # Plaid's dynamic models raise ApiAttributeError for an optional field
    # that's entirely absent from the response (not just null) — getattr
    # with a default sidesteps that instead of a plain attribute access.
    merchant_name = getattr(stream, "merchant_name", None) or stream.description
    normalized_name = normalize_merchant(merchant_name)
    average_cost = Decimal(str(abs(stream.average_amount.amount)))
    currency = (
        getattr(stream.average_amount, "iso_currency_code", None)
        or getattr(stream.average_amount, "unofficial_currency_code", None)
        or "USD"
    )
    billing_cycle = str(stream.frequency).lower()
    status = SubscriptionStatus.ACTIVE if stream.is_active else SubscriptionStatus.CANCELLED

    with SessionLocal() as session:
        subscription = (
            session.query(Subscription)
            .filter_by(user_id=user_id, normalized_name=normalized_name)
            .one_or_none()
        )
        if subscription is None:
            subscription = Subscription(
                user_id=user_id,
                merchant_name=merchant_name,
                normalized_name=normalized_name,
                average_cost=average_cost,
                currency=currency,
                billing_cycle=billing_cycle,
                status=status,
            )
            session.add(subscription)
        else:
            if subscription.average_cost != average_cost:
                subscription.last_price_change_amount = average_cost - subscription.average_cost
            subscription.average_cost = average_cost
            subscription.currency = currency
            subscription.billing_cycle = billing_cycle
            subscription.status = status

        subscription.last_charge = stream.last_date
        subscription.next_expected_charge = stream.predicted_next_date
        session.commit()
        session.refresh(subscription)
        return subscription


def find_active_subscription(
    session: Session, user_id: uuid.UUID, normalized_merchant: str
) -> uuid.UUID | None:
    """Cheap per-transaction lookup against already-detected subscriptions — no Plaid call.
    Discovering *new* recurring streams still requires save_subscription() via the
    Plaid recurring-transactions endpoint; this only links against what's already known.
    Takes the caller's session (see transaction_analysis.py's save_analysis/save_scores)
    since it's called alongside them on the single-transaction critical path.
    """
    subscription = (
        session.query(Subscription)
        .filter_by(
            user_id=user_id,
            normalized_name=normalized_merchant,
            status=SubscriptionStatus.ACTIVE,
        )
        .one_or_none()
    )
    return subscription.id if subscription is not None else None


def link_transactions_to_subscription(
    subscription_id: uuid.UUID, user_id: uuid.UUID, plaid_transaction_ids: list[str]
) -> int:
    """Retroactively sets transaction_analysis.subscription_id for transactions
    that were already scored before this subscription was detected -- this can
    run well after those transactions' scoring history was cached (subscription
    detection is dispatched after a sync batch's process_transaction tasks), so
    it must invalidate that cache: without it, is_known_subscription_merchant
    (feeds the smart-purchase score's recurring bonus) would silently lag
    behind reality until the cache's TTL expires.
    """
    with SessionLocal() as session:
        transaction_ids = [
            row[0]
            for row in session.query(Transaction.id)
            .filter(Transaction.plaid_transaction_id.in_(plaid_transaction_ids))
            .all()
        ]
        for transaction_id in transaction_ids:
            save_analysis(session, transaction_id, subscription_id=subscription_id)
        session.commit()

    if transaction_ids:
        invalidate_history(user_id)
    return len(transaction_ids)
