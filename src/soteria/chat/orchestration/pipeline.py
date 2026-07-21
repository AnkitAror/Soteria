"""The sole orchestrator for answering a chat question.

Every other module in chat/ (intent_classification, schema_introspection,
sql_generation, sql_safety, sql_execution, answer_synthesis, rag/*,
services/sessions) is a pure function library that never calls another
chat/* module directly -- answer_question is the only place that sequences
them, so the control flow (what runs, in what order, under what condition)
stays legible in one place.
"""

import logging
import uuid

from soteria.chat.orchestration.answer_synthesis import synthesize_answer
from soteria.chat.orchestration.intent_classification import classify_intent
from soteria.chat.orchestration.schema_introspection import get_view_schema
from soteria.chat.orchestration.sql_execution import execute_sql
from soteria.chat.orchestration.sql_generation import generate_sql
from soteria.chat.orchestration.sql_safety import UnsafeSqlError, validate_sql
from soteria.chat.rag.embeddings import embed_text
from soteria.chat.rag.retrieval import retrieve_relevant
from soteria.chat.services.sessions import append_message, get_recent_turns
from soteria.chat.types import RetrievedItem
from soteria.db.models.chat_messages import ChatMessage

logger = logging.getLogger(__name__)


def answer_question(user_id: uuid.UUID, session_id: uuid.UUID, question: str) -> ChatMessage:
    history = get_recent_turns(session_id)
    append_message(session_id, role="user", message=question)

    intent = classify_intent(question)

    retrieved_context: list[RetrievedItem] = []
    if intent.needs_context:
        try:
            query_embedding = embed_text(question)
            retrieved_context = retrieve_relevant(user_id, query_embedding)
        except Exception:
            logger.exception("Retrieval failed for question; continuing without context")

    sql_rows: list[dict] = []
    sql_generated: str | None = None
    if intent.needs_sql:
        try:
            schema = get_view_schema()
            candidate_sql = generate_sql(question, schema, history)
            if candidate_sql:
                sql_generated = validate_sql(candidate_sql)
                sql_rows = execute_sql(user_id, sql_generated)
        except UnsafeSqlError:
            logger.warning("Generated SQL failed safety validation for question=%r", question)
            sql_generated = None
        except Exception:
            logger.exception("SQL execution failed for question; continuing without data")
            sql_generated = None

    answer_with_citations = synthesize_answer(question, sql_rows, retrieved_context)

    return append_message(
        session_id,
        role="assistant",
        message=answer_with_citations.answer,
        sql_generated=sql_generated,
        citations=answer_with_citations.citations,
    )
