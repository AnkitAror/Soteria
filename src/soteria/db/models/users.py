"""`users` table model — see references/db_schema.md."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.bank_accounts import BankAccount
    from soteria.db.models.chat_sessions import ChatSession
    from soteria.db.models.embeddings import Embedding
    from soteria.db.models.insights import Insight
    from soteria.db.models.plaid_items import PlaidItem
    from soteria.db.models.subscriptions import Subscription
    from soteria.db.models.transactions import Transaction


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)

    plaid_items: Mapped[list["PlaidItem"]] = relationship(back_populates="user")
    bank_accounts: Mapped[list["BankAccount"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    insights: Mapped[list["Insight"]] = relationship(back_populates="user")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="user")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
