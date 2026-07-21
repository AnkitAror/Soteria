"""Chat session/message persistence and per-user ownership scoping.

Mirrors the ownership-check pattern used by
api/routers/plaid_items.py::_get_owned_item, but as a plain domain function
(raises SessionNotFoundError rather than HTTPException) so it stays
reusable from both the API router and pipeline.py.
"""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from soteria.chat.types import ChatTurn, Citation
from soteria.db.models.chat_messages import ChatMessage
from soteria.db.models.chat_sessions import ChatSession
from soteria.db.session import SessionLocal

_HISTORY_LIMIT = 10
_TITLE_MAX_LENGTH = 60


class SessionNotFoundError(Exception):
    pass


def create_session(user_id: uuid.UUID, title: str | None = None) -> ChatSession:
    with SessionLocal() as session:
        chat_session = ChatSession(user_id=user_id, title=title)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session


def list_sessions(user_id: uuid.UUID) -> list[ChatSession]:
    with SessionLocal() as session:
        return list(
            session.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
            ).all()
        )


def get_session(session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    with SessionLocal() as session:
        return _owned_session(session, session_id, user_id)


def rename_session(session_id: uuid.UUID, user_id: uuid.UUID, title: str) -> ChatSession:
    with SessionLocal() as session:
        chat_session = _owned_session(session, session_id, user_id)
        chat_session.title = title
        session.commit()
        session.refresh(chat_session)
        return chat_session


def delete_session(session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        chat_session = _owned_session(session, session_id, user_id)
        session.delete(chat_session)
        session.commit()


def get_messages(session_id: uuid.UUID, user_id: uuid.UUID) -> list[ChatMessage]:
    with SessionLocal() as session:
        _owned_session(session, session_id, user_id)
        return list(
            session.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            ).all()
        )


def get_recent_turns(session_id: uuid.UUID, limit: int = _HISTORY_LIMIT) -> list[ChatTurn]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()
    return [ChatTurn(role=row.role, content=row.message) for row in reversed(rows)]


def append_message(
    session_id: uuid.UUID,
    role: str,
    message: str,
    sql_generated: str | None = None,
    citations: list[Citation] | None = None,
) -> ChatMessage:
    with SessionLocal() as session:
        chat_message = ChatMessage(
            session_id=session_id,
            role=role,
            message=message,
            sql_generated=sql_generated,
            citations_json=[asdict(c) for c in citations] if citations else None,
        )
        session.add(chat_message)

        chat_session = session.get(ChatSession, session_id)
        if chat_session is not None:
            chat_session.updated_at = datetime.now(UTC)
            if chat_session.title is None and role == "user":
                chat_session.title = message[:_TITLE_MAX_LENGTH]

        session.commit()
        session.refresh(chat_message)
        return chat_message


def _owned_session(session: Session, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user_id:
        raise SessionNotFoundError(str(session_id))
    return chat_session
