"""Embedding generation for RAG retrieval.

Only ever called for INSIGHT and CHAT_MESSAGE objects (see insights/
persistence.py's hook and chat/services/sessions.py) -- transactions are
never embedded. They're structured data SQL already answers precisely, and
embedding every transaction row would be pure cost for no retrieval benefit
over the SQL path.
"""

import hashlib
import uuid

from google.genai import types
from sqlalchemy import select

from soteria.chat.gemini_client import embed_content
from soteria.core.config import get_settings
from soteria.db.models.embeddings import EMBEDDING_DIMENSIONS, Embedding, EmbeddingObjectType
from soteria.db.session import SessionLocal


def embed_text(text: str) -> list[float]:
    response = embed_content(
        model=get_settings().gemini_embedding_model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    if not response.embeddings or response.embeddings[0].values is None:
        raise RuntimeError("Gemini returned no embedding")
    return response.embeddings[0].values


def store_embedding(
    user_id: uuid.UUID,
    object_type: EmbeddingObjectType,
    object_id: uuid.UUID,
    text: str,
) -> None:
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    with SessionLocal() as session:
        existing = session.scalar(
            select(Embedding).where(
                Embedding.user_id == user_id,
                Embedding.object_type == object_type,
                Embedding.object_id == object_id,
            )
        )
        if existing is not None and existing.content_hash == content_hash:
            return  # content unchanged since it was last embedded

        vector = embed_text(text)

        if existing is not None:
            existing.embedding = vector
            existing.content_hash = content_hash
        else:
            session.add(
                Embedding(
                    user_id=user_id,
                    object_type=object_type,
                    object_id=object_id,
                    embedding=vector,
                    content_hash=content_hash,
                )
            )
        session.commit()
