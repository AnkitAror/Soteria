"""`insights` table model — see references/db_schema.md."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.users import User


class Insight(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "insights"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    # Which spending category this insight is about (e.g. "Food"), for
    # grouping into category cards. NULL for account/cash-flow-level
    # insights (low_balance_forecast, spending_exceeds_income, savings_trend,
    # spending_above_normal, the overall merchant_concentration) that aren't
    # about any one category.
    category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="insights")
