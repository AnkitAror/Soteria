"""Celery Beat task: periodically fan insight generation out to every user.

process_transaction.delay() calls from sync_item_transactions() are async
and uncoordinated — multiple Plaid items/webhooks for the same user can be
syncing concurrently, so there's no reliable "this user's sync batch is
fully scored" event to trigger insight generation off of. Instead, this
recomputes every user's insights from scratch on an interval (see
celery_app.py's beat_schedule) — cheap at current volume, same tradeoff the
rest of this codebase already makes for history refetching/re-normalization.
"""

from soteria.db.models.transactions import Transaction
from soteria.db.session import SessionLocal
from soteria.worker.celery_app import app
from soteria.worker.tasks.generate_insights import generate_insights_task


@app.task(
    name="insights.fan_out_generation",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def fan_out_insight_generation() -> None:
    with SessionLocal() as session:
        user_ids = [
            row[0]
            for row in session.query(Transaction.user_id)
            .filter(Transaction.removed_at.is_(None))
            .distinct()
            .all()
        ]

    for user_id in user_ids:
        generate_insights_task.delay(str(user_id))

    print(f"Fanned out insight generation for {len(user_ids)} user(s)")
