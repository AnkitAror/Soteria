"""`merchant_profiles` table model — see references/db_schema.md."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.transactions import Transaction


class MerchantProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchant_profiles"

    normalized_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    merchant_type: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="merchant")
