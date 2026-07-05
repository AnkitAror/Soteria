"""`chat_messages` table model — see references/db_schema.md."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from soteria.db.base import Base
from soteria.db.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from soteria.db.models.chat_sessions import ChatSession


class ChatMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    # Generated SQL must be executed through a restricted, read-only Postgres role
    # scoped to the requesting user (per-user-filtered views or RLS) — see
    # references/db_schema.md's execution safety note. Enforced at the app/infra
    # layer, not by this column.
    sql_generated: Mapped[str | None] = mapped_column(String, nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
