"""Spending chatbot endpoints: sessions + synchronous question/answer."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from soteria.chat.orchestration.pipeline import answer_question
from soteria.chat.services.sessions import (
    SessionNotFoundError,
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    rename_session,
)
from soteria.chat.usage import get_usage_today
from soteria.core.auth import get_current_user_id
from soteria.db.models.chat_messages import ChatMessage
from soteria.db.models.chat_sessions import ChatSession

router = APIRouter(prefix="/api", tags=["chat"])


class ChatSessionSummary(BaseModel):
    id: str
    title: str | None
    updated_at: str


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionSummary]


class CreateChatSessionRequest(BaseModel):
    title: str | None = None


class RenameChatSessionRequest(BaseModel):
    title: str


class CitationOut(BaseModel):
    type: str
    ref_id: str | None
    label: str
    detail: str


class ChatMessageOut(BaseModel):
    id: str
    role: str
    message: str
    sql_generated: str | None
    citations: list[CitationOut]
    created_at: str


class ChatMessagesResponse(BaseModel):
    messages: list[ChatMessageOut]


class AskQuestionRequest(BaseModel):
    question: str


class UsageResponse(BaseModel):
    used: int
    limit: int
    remaining: int


def _session_summary(session: ChatSession) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=str(session.id),
        title=session.title,
        updated_at=session.updated_at.isoformat(),
    )


def _message_out(message: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=str(message.id),
        role=message.role,
        message=message.message,
        sql_generated=message.sql_generated,
        citations=[CitationOut(**c) for c in (message.citations_json or [])],
        created_at=message.created_at.isoformat(),
    )


@router.get("/chat/usage")
def get_chat_usage(user_id: uuid.UUID = Depends(get_current_user_id)) -> UsageResponse:
    status = get_usage_today()
    return UsageResponse(used=status.used, limit=status.limit, remaining=status.remaining)


@router.get("/chat/sessions")
def list_chat_sessions(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatSessionsResponse:
    sessions = list_sessions(user_id)
    return ChatSessionsResponse(sessions=[_session_summary(s) for s in sessions])


@router.post("/chat/sessions")
def create_chat_session(
    body: CreateChatSessionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatSessionSummary:
    session = create_session(user_id, title=body.title)
    return _session_summary(session)


@router.get("/chat/sessions/{session_id}/messages")
def get_chat_messages(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessagesResponse:
    try:
        messages = get_messages(session_id, user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    return ChatMessagesResponse(messages=[_message_out(m) for m in messages])


@router.post("/chat/sessions/{session_id}/messages")
def ask_question(
    session_id: uuid.UUID,
    body: AskQuestionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatMessageOut:
    try:
        get_messages(session_id, user_id)  # ownership check; 404s before any LLM calls
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc

    answer = answer_question(user_id, session_id, body.question)
    return _message_out(answer)


@router.patch("/chat/sessions/{session_id}")
def rename_chat_session(
    session_id: uuid.UUID,
    body: RenameChatSessionRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ChatSessionSummary:
    try:
        session = rename_session(session_id, user_id, body.title)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    return _session_summary(session)


@router.delete("/chat/sessions/{session_id}", status_code=204)
def delete_chat_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    try:
        delete_session(session_id, user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
