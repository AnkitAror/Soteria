"""Celery application instance."""

from celery import Celery

from soteria.core.config import get_settings

settings = get_settings()

app = Celery(
    "soteria",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["soteria.worker.tasks.plaid_sync"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)
