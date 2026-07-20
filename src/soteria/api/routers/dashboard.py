"""Dashboard endpoints: account summary, monthly spending, spending by category.

Reuses the user-scoped aggregation helpers in insights/aggregation.py rather
than duplicating query logic — those are already exercised by the insight
generator against the same tables.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from soteria.core.auth import get_current_user_id
from soteria.db.models.bank_accounts import BankAccount
from soteria.db.session import SessionLocal
from soteria.insights.aggregation import monthly_cash_flow, monthly_category_totals, shift_month

router = APIRouter(prefix="/api", tags=["dashboard"])


class BankAccountSummary(BaseModel):
    id: str
    institution_name: str
    account_name: str
    account_type: str
    account_subtype: str | None
    current_balance: str | None
    available_balance: str | None
    currency: str


class AccountsResponse(BaseModel):
    accounts: list[BankAccountSummary]


class SpendingSummaryResponse(BaseModel):
    month: str
    total_spend: str
    prior_month_total_spend: str
    percent_change: float | None


class CategorySpend(BaseModel):
    category: str
    total: str


class SpendingByCategoryResponse(BaseModel):
    month: str
    categories: list[CategorySpend]


def _parse_month(month: str | None) -> date:
    if month is None:
        today = date.today()
        return date(today.year, today.month, 1)
    year, mon = month.split("-")
    return date(int(year), int(mon), 1)


@router.get("/accounts")
def list_accounts(user_id: uuid.UUID = Depends(get_current_user_id)) -> AccountsResponse:
    with SessionLocal() as session:
        bank_accounts = (
            session.query(BankAccount)
            .filter(BankAccount.user_id == user_id, BankAccount.deleted_at.is_(None))
            .order_by(BankAccount.account_type, BankAccount.account_name)
            .all()
        )
        return AccountsResponse(
            accounts=[
                BankAccountSummary(
                    id=str(account.id),
                    institution_name=account.institution_name,
                    account_name=account.account_name,
                    account_type=account.account_type,
                    account_subtype=account.account_subtype,
                    current_balance=str(account.current_balance)
                    if account.current_balance is not None
                    else None,
                    available_balance=str(account.available_balance)
                    if account.available_balance is not None
                    else None,
                    currency=account.currency,
                )
                for account in bank_accounts
            ]
        )


@router.get("/dashboard/spending-summary")
def spending_summary(
    month: str | None = None, user_id: uuid.UUID = Depends(get_current_user_id)
) -> SpendingSummaryResponse:
    target_month = _parse_month(month)
    prior_month = shift_month(target_month, -1)

    with SessionLocal() as session:
        cash_flow = monthly_cash_flow(session, user_id, months=2, today=target_month)

    zero_flow = (Decimal("0"), Decimal("0"))
    _, current_spend = cash_flow.get((target_month.year, target_month.month), zero_flow)
    _, prior_spend = cash_flow.get((prior_month.year, prior_month.month), zero_flow)

    percent_change: float | None = None
    if prior_spend:
        percent_change = float((current_spend - prior_spend) / prior_spend * 100)

    return SpendingSummaryResponse(
        month=target_month.isoformat()[:7],
        total_spend=str(current_spend),
        prior_month_total_spend=str(prior_spend),
        percent_change=percent_change,
    )


@router.get("/dashboard/spending-by-category")
def spending_by_category(
    month: str | None = None, user_id: uuid.UUID = Depends(get_current_user_id)
) -> SpendingByCategoryResponse:
    target_month = _parse_month(month)

    with SessionLocal() as session:
        totals = monthly_category_totals(session, user_id, months=1, today=target_month)

    categories = [
        CategorySpend(category=category, total=str(stat.total))
        for (year, mon, category), stat in totals.items()
        if year == target_month.year and mon == target_month.month
    ]
    categories.sort(key=lambda c: float(c.total), reverse=True)

    return SpendingByCategoryResponse(
        month=target_month.isoformat()[:7],
        categories=categories,
    )
