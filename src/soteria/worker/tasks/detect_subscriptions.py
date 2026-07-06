"""Celery task: detect recurring subscriptions for a Plaid Item asynchronously.

Takes Plaid's own item_id string, matching the same id-passing pattern as
plaid.sync_plaid_item.
"""

from soteria.plaid.items import get_plaid_item_by_item_id
from soteria.plaid.services.subscription_service import detect_subscriptions
from soteria.worker.celery_app import app


@app.task(
    name="analysis.detect_subscriptions",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def detect_subscriptions_task(item_id: str) -> None:
    plaid_item = get_plaid_item_by_item_id(item_id)
    if plaid_item is None:
        print(f"detect_subscriptions_task: no PlaidItem found for item_id={item_id}; skipping")
        return
    subscriptions = detect_subscriptions(plaid_item)
    print(f"Detected {len(subscriptions)} subscription(s) for item {item_id}")
