"""Insights endpoints: list active insights, dismiss one."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from soteria.core.auth import get_current_user_id
from soteria.db.models.insights import Insight
from soteria.insights.models.aggregates import severity_rank
from soteria.insights.persistence import dismiss_insight, list_active_insights_for_user

router = APIRouter(prefix="/api", tags=["insights"])


class InsightSummary(BaseModel):
    id: str
    type: str
    title: str
    description: str
    severity: str
    priority: int
    category: str | None
    confidence: str | None
    created_at: str
    viewed_at: str | None
    dismissed_at: str | None


class InsightsResponse(BaseModel):
    insights: list[InsightSummary]


def _insight_summary(insight: Insight) -> InsightSummary:
    return InsightSummary(
        id=str(insight.id),
        type=insight.type,
        title=insight.title,
        description=insight.description,
        severity=insight.severity,
        priority=severity_rank(insight.severity),
        category=insight.category,
        confidence=str(insight.confidence) if insight.confidence is not None else None,
        created_at=insight.created_at.isoformat(),
        viewed_at=insight.viewed_at.isoformat() if insight.viewed_at else None,
        dismissed_at=insight.dismissed_at.isoformat() if insight.dismissed_at else None,
    )


@router.get("/insights")
def list_insights(user_id: uuid.UUID = Depends(get_current_user_id)) -> InsightsResponse:
    insights = list_active_insights_for_user(user_id)
    return InsightsResponse(insights=[_insight_summary(i) for i in insights])


@router.post("/insights/{insight_id}/dismiss")
def dismiss(
    insight_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> InsightSummary:
    insight = dismiss_insight(user_id, insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    return _insight_summary(insight)
