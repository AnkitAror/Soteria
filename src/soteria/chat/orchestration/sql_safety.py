"""Validates LLM-generated SQL before it's ever executed.

This is the security-critical layer standing in for a restricted Postgres
role: it guarantees the query is exactly one read-only SELECT (or set
operation of SELECTs), touching only the four user-scoped views, with no
writes/DDL anywhere in the tree (including inside CTEs), no unrecognized
function calls, no locking, and a bounded LIMIT. Anything else raises
UnsafeSqlError rather than being executed.
"""

import sqlglot
from sqlglot import exp

from soteria.chat.orchestration.schema_introspection import ALLOWED_VIEWS

_READ_ONLY_QUERY_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
)
_MAX_ROWS = 500


class UnsafeSqlError(ValueError):
    pass


def validate_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";")
    if not sql:
        raise UnsafeSqlError("empty SQL")

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSqlError(f"unparseable SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeSqlError("exactly one statement is required")

    stmt = statements[0]

    if not isinstance(stmt, _READ_ONLY_QUERY_TYPES):
        raise UnsafeSqlError(f"only SELECT is allowed, got {type(stmt).__name__}")

    if any(stmt.find_all(*_FORBIDDEN_NODE_TYPES)):
        raise UnsafeSqlError("writes/DDL are not allowed")

    if stmt.args.get("locks"):
        raise UnsafeSqlError("row locking is not allowed")

    if any(select.args.get("into") for select in stmt.find_all(exp.Select)):
        raise UnsafeSqlError("SELECT INTO is not allowed")

    tables = {table.name for table in stmt.find_all(exp.Table)}
    disallowed = tables - set(ALLOWED_VIEWS)
    if disallowed:
        raise UnsafeSqlError(f"disallowed table(s): {', '.join(sorted(disallowed))}")

    if any(stmt.find_all(exp.Anonymous)):
        names = {f.name for f in stmt.find_all(exp.Anonymous)}
        raise UnsafeSqlError(f"disallowed function(s): {', '.join(sorted(names))}")

    assert isinstance(stmt, exp.Query)
    return _enforce_row_limit(stmt)


def _enforce_row_limit(stmt: exp.Query) -> str:
    limit = stmt.args.get("limit")
    if limit is None:
        stmt = stmt.limit(_MAX_ROWS)
    else:
        try:
            requested = int(limit.expression.this)
        except (AttributeError, TypeError, ValueError):
            requested = _MAX_ROWS + 1
        if requested > _MAX_ROWS:
            stmt.set("limit", exp.Limit(expression=exp.Literal.number(_MAX_ROWS)))

    return stmt.sql(dialect="postgres")
