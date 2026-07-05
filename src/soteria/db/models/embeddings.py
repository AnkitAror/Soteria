"""`embeddings` table model (pgvector) — see references/db_schema.md."""

import enum
import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.users import User


class EmbeddingObjectType(enum.StrEnum):
    TRANSACTION = "transaction"
    MERCHANT = "merchant"
    INSIGHT = "insight"
    CHAT_MESSAGE = "chat_message"


# Sized for OpenAI text-embedding-3-small; adjust if a different model is chosen.
EMBEDDING_DIMENSIONS = 1536


class Embedding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "embeddings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    object_type: Mapped[EmbeddingObjectType] = mapped_column(
        Enum(EmbeddingObjectType, native_enum=False, validate_strings=True), nullable=False
    )
    # Polymorphic reference: targets transactions/merchant_profiles/insights/chat_messages
    # depending on object_type, so no single FK constraint applies here.
    object_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship(back_populates="embeddings")
