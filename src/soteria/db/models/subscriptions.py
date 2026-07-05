"""`subscriptions` table model — see references/db_schema.md."""

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.transaction_analysis import TransactionAnalysis
    from soteria.db.models.users import User


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String, nullable=False)
    last_charge: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_expected_charge: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_price_change_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    transaction_analyses: Mapped[list["TransactionAnalysis"]] = relationship(
        back_populates="subscription"
    )
