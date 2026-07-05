"""`users` table model — see references/db_schema.md."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.bank_accounts import BankAccount
    from soteria.db.models.plaid_items import PlaidItem
    from soteria.db.models.transactions import Transaction


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)

    plaid_items: Mapped[list["PlaidItem"]] = relationship(back_populates="user")
    bank_accounts: Mapped[list["BankAccount"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
