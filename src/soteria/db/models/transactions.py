"""`transactions` table model — see references/db_schema.md."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.bank_accounts import BankAccount
    from soteria.db.models.users import User


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_accounts.id"), nullable=False, index=True
    )
    plaid_transaction_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # No FK constraint yet: merchant_profiles is out of scope/unimplemented.
    # Add ForeignKey("merchant_profiles.id") + relationship once that model lands.
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    authorized_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    location_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    account: Mapped["BankAccount"] = relationship(back_populates="transactions")
