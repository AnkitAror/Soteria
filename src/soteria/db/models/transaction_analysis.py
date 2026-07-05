"""`transaction_analysis` table model — see references/db_schema.md."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.subscriptions import Subscription
    from soteria.db.models.transactions import Transaction


class TransactionAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transaction_analysis"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id"), unique=True, nullable=False, index=True
    )
    normalized_merchant: Mapped[str | None] = mapped_column(String, nullable=True)
    normalized_category: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id"), nullable=True, index=True
    )
    fraud_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    fraud_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    smart_purchase_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    price_competitiveness_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    behavioral_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    merchant_frequency: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    category_monthly_average: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    spending_deviation: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    analysis_version: Mapped[str] = mapped_column(String, nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="analysis")
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="transaction_analyses"
    )
