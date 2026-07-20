"""Transactions list endpoint: paginated, with per-transaction analysis scores."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from soteria.core.auth import get_current_user_id
from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal

router = APIRouter(prefix="/api", tags=["transactions"])

MAX_LIMIT = 200


class TransactionAnalysisSummary(BaseModel):
    anomaly_score: str | None
    behavioral_score: str | None
    is_subscription: bool


class TransactionListItem(BaseModel):
    id: str
    description: str
    merchant_name: str | None
    amount: str
    currency: str
    transaction_date: str
    pending: bool
    category: str | None
    analysis: TransactionAnalysisSummary | None


class TransactionsResponse(BaseModel):
    items: list[TransactionListItem]
    total: int
    limit: int
    offset: int


def _transaction_list_item(transaction: Transaction) -> TransactionListItem:
    analysis: TransactionAnalysisSummary | None = None
    if transaction.analysis is not None:
        analysis = TransactionAnalysisSummary(
            anomaly_score=str(transaction.analysis.anomaly_score)
            if transaction.analysis.anomaly_score is not None
            else None,
            behavioral_score=str(transaction.analysis.behavioral_score)
            if transaction.analysis.behavioral_score is not None
            else None,
            is_subscription=transaction.analysis.subscription_id is not None,
        )

    return TransactionListItem(
        id=str(transaction.id),
        description=transaction.description,
        merchant_name=transaction.merchant_name,
        amount=str(transaction.amount),
        currency=transaction.currency,
        transaction_date=transaction.transaction_date.isoformat(),
        pending=transaction.pending,
        category=transaction.category,
        analysis=analysis,
    )


@router.get("/transactions")
def list_transactions(
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    search: str | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> TransactionsResponse:
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    with SessionLocal() as session:
        filters = [Transaction.user_id == user_id, Transaction.removed_at.is_(None)]
        if category is not None:
            filters.append(Transaction.category == category)
        if search is not None:
            pattern = f"%{search}%"
            filters.append(
                (Transaction.merchant_name.ilike(pattern))
                | (Transaction.description.ilike(pattern))
            )

        total = session.query(func.count(Transaction.id)).filter(*filters).scalar() or 0

        transactions = (
            session.query(Transaction)
            .options(joinedload(Transaction.analysis))
            .filter(*filters)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return TransactionsResponse(
            items=[_transaction_list_item(t) for t in transactions],
            total=total,
            limit=limit,
            offset=offset,
        )
