"""Lightweight, session-independent value types shared across chat/*.

ORM objects are tied to the SQLAlchemy session that loaded them and can't
safely cross the boundaries between orchestration/rag/services modules
(session.py's convention is to build plain data before a `with SessionLocal()`
block ends -- see db/session.py). These are that plain data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatTurn:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Citation:
    type: str  # "insight" | "chat_message" | "sql_result"
    ref_id: str | None
    label: str
    detail: str


@dataclass(frozen=True)
class RetrievedItem:
    object_type: str  # "insight" | "chat_message"
    object_id: str
    content: str


@dataclass(frozen=True)
class AnswerWithCitations:
    answer: str
    citations: list[Citation]
