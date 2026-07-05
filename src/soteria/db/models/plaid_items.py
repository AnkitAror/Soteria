"""`plaid_items` table model — see references/db_schema.md."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.bank_accounts import BankAccount
    from soteria.db.models.users import User


class PlaidItemStatus(enum.StrEnum):
    ACTIVE = "active"
    LOGIN_REQUIRED = "login_required"
    ERROR = "error"
    REVOKED = "revoked"


class PlaidItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plaid_items"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plaid_item_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    plaid_access_token: Mapped[str] = mapped_column(String, nullable=False)
    institution_id: Mapped[str] = mapped_column(String, nullable=False)
    institution_name: Mapped[str] = mapped_column(String, nullable=False)
    sync_cursor: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[PlaidItemStatus] = mapped_column(
        Enum(PlaidItemStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=PlaidItemStatus.ACTIVE,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="plaid_items")
    bank_accounts: Mapped[list["BankAccount"]] = relationship(back_populates="plaid_item")
