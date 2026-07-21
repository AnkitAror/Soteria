"""Unit tests for chat/orchestration/sql_safety.validate_sql — pure function,
no DB, no LLM. This is the security-critical layer standing in for a
restricted Postgres role, so it's tested directly rather than only through
the non-deterministic live-LLM path.
"""

import pytest

from soteria.chat.orchestration.sql_safety import UnsafeSqlError, validate_sql


def test_accepts_single_select_against_allowed_view() -> None:
    out = validate_sql("SELECT id, amount FROM v_transactions WHERE amount > 10")

    assert "SELECT" in out
    assert "v_transactions" in out


def test_accepts_aggregate_query_with_group_by() -> None:
    out = validate_sql("SELECT SUM(amount), category FROM v_transactions GROUP BY category")

    assert "SUM" in out.upper()


def test_injects_limit_when_missing() -> None:
    out = validate_sql("SELECT * FROM v_transactions")

    assert "LIMIT 500" in out


def test_caps_limit_when_over_max() -> None:
    out = validate_sql("SELECT * FROM v_transactions LIMIT 999999")

    assert "LIMIT 500" in out
    assert "999999" not in out


def test_keeps_limit_when_under_max() -> None:
    out = validate_sql("SELECT * FROM v_transactions LIMIT 10")

    assert "LIMIT 10" in out


def test_accepts_union_of_allowed_views() -> None:
    out = validate_sql("SELECT id FROM v_transactions UNION SELECT id FROM v_subscriptions")

    assert out  # doesn't raise


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM v_transactions; DROP TABLE users;",
        "SELECT * FROM v_transactions; SELECT * FROM v_insights;",
    ],
)
def test_rejects_multiple_statements(sql: str) -> None:
    with pytest.raises(UnsafeSqlError, match="exactly one statement"):
        validate_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM v_transactions",
        "UPDATE v_transactions SET amount = 0",
        "INSERT INTO v_transactions (amount) VALUES (1)",
        "DROP VIEW v_transactions",
    ],
)
def test_rejects_writes_and_ddl(sql: str) -> None:
    with pytest.raises(UnsafeSqlError):
        validate_sql(sql)


def test_rejects_write_hidden_inside_a_cte() -> None:
    sql = "WITH x AS (INSERT INTO users(id) VALUES ('a') RETURNING id) SELECT * FROM x"

    with pytest.raises(UnsafeSqlError, match="writes/DDL"):
        validate_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users",
        "SELECT * FROM plaid_items",
        "SELECT * FROM v_transactions t JOIN users u ON u.id = t.user_id",
    ],
)
def test_rejects_tables_outside_the_allow_list(sql: str) -> None:
    with pytest.raises(UnsafeSqlError, match="disallowed table"):
        validate_sql(sql)


def test_rejects_unrecognized_functions() -> None:
    with pytest.raises(UnsafeSqlError, match="disallowed function"):
        validate_sql("SELECT pg_sleep(5)")


def test_rejects_select_for_update() -> None:
    with pytest.raises(UnsafeSqlError, match="locking"):
        validate_sql("SELECT * FROM v_transactions FOR UPDATE")


def test_rejects_empty_sql() -> None:
    with pytest.raises(UnsafeSqlError):
        validate_sql("")


def test_rejects_unparseable_sql() -> None:
    with pytest.raises(UnsafeSqlError):
        validate_sql("SELEKT * FROM v_transactions GARBLED")
