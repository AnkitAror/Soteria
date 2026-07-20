"""SQLAlchemy engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from soteria.core.config import get_settings


def _psycopg_url(database_url: str) -> str:
    """Force the psycopg (v3) driver regardless of the URL's declared scheme."""
    return make_url(database_url).set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


engine = create_engine(
    _psycopg_url(get_settings().database_url),
    pool_pre_ping=True,
    # Belt-and-suspenders with pool_pre_ping against Supabase's own
    # connection lifetime limits: a connection that's about to be reused
    # past this age gets replaced instead of risking a stale-connection
    # error. The actual fix for connection-pool exhaustion under Supabase's
    # 15-connection session-mode pooler is capping Celery worker
    # concurrency (see docker-compose.yml/Makefile) — a fully idle
    # connection that's never checked out again isn't touched by this.
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine)
