"""One-off connectivity check against DATABASE_URL. Reads only; no tables touched.

Usage: uv run python scripts/check_db_connection.py
"""

from sqlalchemy import text

from soteria.db.session import engine


def main() -> None:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
    print("Connected successfully.")
    print(version)


if __name__ == "__main__":
    main()
