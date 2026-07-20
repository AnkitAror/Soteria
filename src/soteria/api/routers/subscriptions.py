"""Subscriptions list endpoint: detected recurring charges, normalized to a
monthly-equivalent cost so different billing cycles are comparable at a glance.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from soteria.core.auth import get_current_user_id
from soteria.db.models.merchant_profiles import MerchantProfile
from soteria.db.models.subscriptions import Subscription, SubscriptionStatus
from soteria.db.session import SessionLocal

router = APIRouter(prefix="/api", tags=["subscriptions"])

# Multiplier to convert a subscription's per-charge average_cost into a
# monthly-equivalent figure. Unrecognized/unknown cycles fall back to 1
# (treated as already-monthly) rather than distorting the total.
_MONTHLY_MULTIPLIERS = {
    "weekly": Decimal(52) / Decimal(12),
    "biweekly": Decimal(26) / Decimal(12),
    "semi_monthly": Decimal(2),
    "monthly": Decimal(1),
    "annually": Decimal(1) / Decimal(12),
}


def _monthly_cost(average_cost: Decimal, billing_cycle: str) -> Decimal:
    multiplier = _MONTHLY_MULTIPLIERS.get(billing_cycle, Decimal(1))
    return (average_cost * multiplier).quantize(Decimal("0.01"))


class SubscriptionSummary(BaseModel):
    id: str
    merchant_name: str
    category: str | None
    status: str
    billing_cycle: str
    average_cost: str
    monthly_cost: str
    currency: str
    last_charge: str | None
    next_expected_charge: str | None
    last_price_change_amount: str | None


class SubscriptionsResponse(BaseModel):
    subscriptions: list[SubscriptionSummary]
    total_monthly_cost: str


@router.get("/subscriptions")
def list_subscriptions(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SubscriptionsResponse:
    with SessionLocal() as session:
        rows = (
            session.query(Subscription, MerchantProfile.category)
            .outerjoin(
                MerchantProfile, MerchantProfile.normalized_name == Subscription.normalized_name
            )
            .filter(Subscription.user_id == user_id)
            .order_by(
                Subscription.status,
                Subscription.next_expected_charge.is_(None),
                Subscription.next_expected_charge,
                Subscription.merchant_name,
            )
            .all()
        )

    summaries = []
    total_monthly_cost = Decimal("0")
    for subscription, category in rows:
        monthly_cost = _monthly_cost(subscription.average_cost, subscription.billing_cycle)
        if subscription.status == SubscriptionStatus.ACTIVE:
            total_monthly_cost += monthly_cost

        summaries.append(
            SubscriptionSummary(
                id=str(subscription.id),
                merchant_name=subscription.merchant_name,
                category=category,
                status=subscription.status.value,
                billing_cycle=subscription.billing_cycle,
                average_cost=str(subscription.average_cost),
                monthly_cost=str(monthly_cost),
                currency=subscription.currency,
                last_charge=subscription.last_charge.isoformat()
                if subscription.last_charge
                else None,
                next_expected_charge=subscription.next_expected_charge.isoformat()
                if subscription.next_expected_charge
                else None,
                last_price_change_amount=str(subscription.last_price_change_amount)
                if subscription.last_price_change_amount is not None
                else None,
            )
        )

    return SubscriptionsResponse(
        subscriptions=summaries,
        total_monthly_cost=str(total_monthly_cost),
    )
