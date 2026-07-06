"""Health-check task: verify the Celery pipeline (broker, worker, serialization) end-to-end."""

from soteria.worker.celery_app import app


@app.task(name="health.ping")
def ping() -> str:
    return "pong"
