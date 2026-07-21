"""One-off: embeds every currently-active insight for every user so older
insights become retrievable by the chatbot's RAG context
(chat/rag/retrieval.py). New insights are embedded automatically going
forward via insights/persistence.py::upsert_insight -- this only needs to
run once, for data that predates that hook. Safe to re-run: store_embedding
skips insights whose content hasn't changed since they were last embedded.

Usage: uv run python scripts/backfill_insight_embeddings.py
"""

from sqlalchemy import select

from soteria.chat.rag.embeddings import store_embedding
from soteria.db.models.embeddings import EmbeddingObjectType
from soteria.db.models.insights import Insight
from soteria.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        insights = session.scalars(select(Insight).where(Insight.dismissed_at.is_(None))).all()

    print(f"Embedding {len(insights)} active insight(s)...")
    for i, insight in enumerate(insights, start=1):
        store_embedding(
            insight.user_id,
            EmbeddingObjectType.INSIGHT,
            insight.id,
            f"{insight.title}: {insight.description}",
        )
        print(f"  [{i}/{len(insights)}] {insight.title}")

    print("Done.")


if __name__ == "__main__":
    main()
