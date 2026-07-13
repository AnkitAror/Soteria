"""Celery task: generate insights for a single user asynchronously.

Takes a user_id, not a transaction_id — unlike process_transaction, this
looks at a user's entire scored transaction/subscription/account picture,
not one row. ORM objects can't cross process boundaries, so this still
passes a primitive string, matching the same id-passing pattern as
plaid.sync_plaid_item and analysis.process_transaction.
"""

import uuid

from soteria.insights.generator import generate_insights
from soteria.worker.celery_app import app


@app.task(
    name="insights.generate_for_user",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_insights_task(user_id: str) -> None:
    insights = generate_insights(uuid.UUID(user_id))
    print(f"Generated/refreshed {len(insights)} insight(s) for user {user_id}")
