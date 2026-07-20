"""Persist `insights` rows with update/expire/replace semantics.

A plain "insert if not already active" dedup would let a still-true finding
go stale for up to expires_in_days (same numbers shown for two weeks), then
spam a duplicate row once it lapses — three "Dining spending increased"
cards instead of one. upsert_insight avoids that by comparing identity_key
(what the insight is about) and value_signature (the specific value
detected) against any currently-active row before deciding what to do.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from soteria.db.models.insights import Insight
from soteria.db.session import SessionLocal
from soteria.insights.models.aggregates import InsightDraft, severity_rank


def _active_insights_query(
    session: Session, user_id: uuid.UUID, insight_type: str, *, now: datetime
) -> Query[Insight]:
    return session.query(Insight).filter(
        Insight.user_id == user_id,
        Insight.type == insight_type,
        Insight.dismissed_at.is_(None),
        or_(Insight.expires_at.is_(None), Insight.expires_at > now),
    )


def upsert_insight(user_id: uuid.UUID, draft: InsightDraft) -> Insight:
    now = datetime.now(UTC)
    metadata = dict(draft.metadata)
    metadata["identity_key"] = draft.identity_key
    metadata["value_signature"] = draft.value_signature

    with SessionLocal() as session:
        candidates = _active_insights_query(session, user_id, draft.type, now=now).all()
        existing = next(
            (
                candidate
                for candidate in candidates
                if (candidate.metadata_json or {}).get("identity_key") == draft.identity_key
            ),
            None,
        )

        if existing is None:
            insight = Insight(
                user_id=user_id,
                type=draft.type,
                title=draft.title,
                description=draft.description,
                severity=draft.severity,
                confidence=draft.confidence,
                category=draft.category,
                metadata_json=metadata,
                expires_at=now + timedelta(days=draft.expires_in_days),
            )
            session.add(insight)
            session.commit()
            session.refresh(insight)
            return insight

        existing_signature = (existing.metadata_json or {}).get("value_signature")
        if existing_signature == draft.value_signature:
            # Same underlying fact, freshly confirmed: refresh the existing row
            # and extend its life rather than inserting a duplicate. created_at
            # (and the row's id) are left untouched so "first detected" stays
            # accurate.
            existing.title = draft.title
            existing.description = draft.description
            existing.severity = draft.severity
            existing.confidence = draft.confidence
            existing.category = draft.category
            existing.metadata_json = metadata
            existing.expires_at = now + timedelta(days=draft.expires_in_days)
            session.commit()
            session.refresh(existing)
            return existing

        # The finding changed materially (e.g. a further subscription price
        # hike, or the spend ratio moved to a new severity bucket): supersede
        # the old row immediately rather than waiting out its natural expiry,
        # and insert a fresh one for the new value.
        existing.expires_at = now
        insight = Insight(
            user_id=user_id,
            type=draft.type,
            title=draft.title,
            description=draft.description,
            severity=draft.severity,
            confidence=draft.confidence,
            category=draft.category,
            metadata_json=metadata,
            expires_at=now + timedelta(days=draft.expires_in_days),
        )
        session.add(insight)
        session.commit()
        session.refresh(insight)
        return insight


def dismiss_insight(user_id: uuid.UUID, insight_id: uuid.UUID) -> Insight | None:
    """Soft-dismiss: sets dismissed_at so the row drops out of
    list_active_insights_for_user without being deleted. Returns None if no
    such insight exists for this user (caller should treat that as 404)."""
    with SessionLocal() as session:
        insight = session.get(Insight, insight_id)
        if insight is None or insight.user_id != user_id:
            return None
        insight.dismissed_at = datetime.now(UTC)
        session.commit()
        session.refresh(insight)
        return insight


def list_active_insights_for_user(user_id: uuid.UUID) -> list[Insight]:
    """Not every insight deserves equal attention — a low balance forecast
    should surface above a 3% coffee spending bump. Ranked by severity
    first; sorted() is stable, so ties keep the query's created_at-desc
    order as the tiebreaker (most recent first within the same severity)."""
    now = datetime.now(UTC)
    with SessionLocal() as session:
        insights = (
            session.query(Insight)
            .filter(
                Insight.user_id == user_id,
                Insight.dismissed_at.is_(None),
                or_(Insight.expires_at.is_(None), Insight.expires_at > now),
            )
            .order_by(Insight.created_at.desc())
            .all()
        )
    return sorted(insights, key=lambda insight: severity_rank(insight.severity))
