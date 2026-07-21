"""pgvector similarity retrieval, scoped to a user's insights and past chat messages.

Only called by pipeline.py, and only when intent_classification.classify_intent
says the question needs semantic context -- not on every request.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from soteria.chat.types import RetrievedItem
from soteria.db.models.chat_messages import ChatMessage
from soteria.db.models.embeddings import Embedding, EmbeddingObjectType
from soteria.db.models.insights import Insight
from soteria.db.session import SessionLocal

_RETRIEVABLE_TYPES = (EmbeddingObjectType.INSIGHT, EmbeddingObjectType.CHAT_MESSAGE)


def retrieve_relevant(
    user_id: uuid.UUID, query_embedding: list[float], top_k: int = 5
) -> list[RetrievedItem]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(Embedding)
            .where(
                Embedding.user_id == user_id,
                Embedding.object_type.in_(_RETRIEVABLE_TYPES),
            )
            .order_by(Embedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        ).all()

        items: list[RetrievedItem] = []
        for row in rows:
            content = _load_content(session, row)
            if content is not None:
                items.append(
                    RetrievedItem(
                        object_type=row.object_type.value,
                        object_id=str(row.object_id),
                        content=content,
                    )
                )
        return items


def _load_content(session: Session, row: Embedding) -> str | None:
    if row.object_type == EmbeddingObjectType.INSIGHT:
        insight = session.get(Insight, row.object_id)
        return f"{insight.title}: {insight.description}" if insight else None
    if row.object_type == EmbeddingObjectType.CHAT_MESSAGE:
        message = session.get(ChatMessage, row.object_id)
        return message.message if message else None
    return None
