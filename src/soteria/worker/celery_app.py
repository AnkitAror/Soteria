"""Celery application instance."""

from celery import Celery

from soteria.core.config import get_settings

settings = get_settings()

app = Celery(
    "soteria",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "soteria.worker.tasks.detect_subscriptions",
        "soteria.worker.tasks.health",
        "soteria.worker.tasks.plaid_sync",
        "soteria.worker.tasks.process_transaction",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    # Retry connecting to the broker on startup instead of failing fast if
    # Redis isn't up yet.
    broker_connection_retry_on_startup=True,
    # Ack after a task finishes, not before — if a worker dies mid-task, the
    # task is redelivered instead of silently lost.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Default retry policy any task can rely on via self.retry() without
    # declaring its own max_retries/default_retry_delay.
    task_annotations={"*": {"max_retries": 3, "default_retry_delay": 30}},
)
