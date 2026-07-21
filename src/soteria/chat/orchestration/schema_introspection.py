"""Introspects the chat-safe views' real columns for the SQL-generation prompt.

Reading from information_schema (rather than a hand-maintained description)
means the prompt can never describe a column that doesn't actually exist on
a view, or omit one that was added later.
"""

from functools import lru_cache

from sqlalchemy import text

from soteria.db.session import SessionLocal

ALLOWED_VIEWS = ("v_transactions", "v_subscriptions", "v_insights", "v_bank_accounts")

_COLUMNS_QUERY = text(
    """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = ANY(:view_names)
    ORDER BY table_name, ordinal_position
    """
)


@lru_cache
def get_view_schema() -> str:
    """Compact `view(col: type, ...)` description of the allow-listed views."""
    with SessionLocal() as session:
        rows = session.execute(_COLUMNS_QUERY, {"view_names": list(ALLOWED_VIEWS)}).all()

    columns_by_view: dict[str, list[str]] = {name: [] for name in ALLOWED_VIEWS}
    for table_name, column_name, data_type in rows:
        columns_by_view.setdefault(table_name, []).append(f"{column_name}: {data_type}")

    return "\n".join(
        f"{view}({', '.join(columns_by_view[view])})"
        for view in ALLOWED_VIEWS
        if columns_by_view[view]
    )
