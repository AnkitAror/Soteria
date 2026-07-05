"""Celery task: sync a Plaid Item's transactions asynchronously.

Webhooks must never do this work inline — see the /plaid/webhook handler in
src/soteria/api/main.py, which enqueues this task instead of calling the
sync service directly.
"""

from soteria.plaid.items import get_plaid_item_by_item_id
from soteria.plaid.services.sync_service import sync_item_transactions
from soteria.worker.celery_app import app


@app.task(name="plaid.sync_plaid_item")
def sync_plaid_item(item_id: str) -> None:
    plaid_item = get_plaid_item_by_item_id(item_id)
    if plaid_item is None:
        print(f"sync_plaid_item: no PlaidItem found for item_id={item_id}; skipping")
        return
    sync_item_transactions(plaid_item)
