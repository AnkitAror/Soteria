"""Maps Plaid's webhook_code values to Soteria's own internal event vocabulary.

Note: because our pipeline is built on /transactions/sync (not the legacy
/transactions/get), all events below currently resolve to the exact same
call — sync_item_transactions() already does the right thing (full vs.
incremental sync, and surfacing removals) purely based on whether
plaid_items.sync_cursor is set. The mapping still exists so the codebase has
its own named concepts, decoupled from Plaid's raw webhook_code strings, and
so each event type has a documented seam if it ever needs to diverge.

INITIAL_UPDATE/DEFAULT_UPDATE/HISTORICAL_UPDATE are the legacy
/transactions/get-era codes Plaid still sends for backward compatibility.
SYNC_UPDATES_AVAILABLE is the modern code Plaid recommends for /sync-based
integrations (confirmed live: Plaid delivers this instead of DEFAULT_UPDATE
in at least some cases) — omitting it silently drops real sync events.
"""

import enum


class SyncEvent(enum.StrEnum):
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    FULL_BACKFILL = "full_backfill"
    SOFT_DELETE = "soft_delete"


WEBHOOK_CODE_TO_EVENT: dict[str, SyncEvent] = {
    "INITIAL_UPDATE": SyncEvent.FULL_SYNC,
    "DEFAULT_UPDATE": SyncEvent.INCREMENTAL_SYNC,
    "SYNC_UPDATES_AVAILABLE": SyncEvent.INCREMENTAL_SYNC,
    "HISTORICAL_UPDATE": SyncEvent.FULL_BACKFILL,
    "TRANSACTIONS_REMOVED": SyncEvent.SOFT_DELETE,
}


def resolve_sync_event(webhook_code: str) -> SyncEvent | None:
    return WEBHOOK_CODE_TO_EVENT.get(webhook_code)
