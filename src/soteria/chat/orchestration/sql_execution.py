"""Executes a validated, view-scoped SQL query for one user.

Must only ever be called with SQL that has already passed
sql_safety.validate_sql. `set_config('app.chat_user_id', ..., true)` scopes
the four v_* views (see the add_chat_views_and_citations migration) to this
user for the lifetime of the transaction -- `SET LOCAL <name> = $1` isn't
valid Postgres syntax (SET doesn't accept a bind parameter for its value),
so set_config() is used instead, which does. statement_timeout bounds a
runaway query.
"""

import uuid

from sqlalchemy import text

from soteria.db.session import SessionLocal

_STATEMENT_TIMEOUT = "5s"


def execute_sql(user_id: uuid.UUID, sql: str) -> list[dict]:
    with SessionLocal() as session:
        session.execute(
            text("SELECT set_config('app.chat_user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )
        session.execute(text(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT}'"))
        result = session.execute(text(sql))
        rows = [dict(row._mapping) for row in result]
        session.rollback()  # read-only: never persist anything from this connection
    return rows
