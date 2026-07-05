"""Celery task: sync a Plaid Item's transactions asynchronously.

Webhooks must never do this work inline — see the /plaid/webhook handler in
src/soteria/api/main.py, which enqueues this task instead of calling the
sync service directly.
"""

from soteria.plaid.items import get_plaid_item
from soteria.plaid.services.sync_service import sync_item_transactions
from soteria.worker.celery_app import app


@app.task(name="plaid.sync_item_transactions")
def sync_plaid_item_transactions(plaid_item_id: str) -> None:
    plaid_item = get_plaid_item(plaid_item_id)
    sync_item_transactions(plaid_item)
