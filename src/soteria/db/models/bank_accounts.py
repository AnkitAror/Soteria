"""`bank_accounts` table model — see references/db_schema.md."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.plaid_items import PlaidItem
    from soteria.db.models.transactions import Transaction
    from soteria.db.models.users import User


class BankAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plaid_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plaid_items.id"), nullable=False, index=True
    )
    plaid_account_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    institution_name: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)
    account_subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    available_balance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="bank_accounts")
    plaid_item: Mapped["PlaidItem"] = relationship(back_populates="bank_accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
