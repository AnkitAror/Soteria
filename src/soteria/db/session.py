"""SQLAlchemy engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from soteria.core.config import get_settings


def _psycopg_url(database_url: str) -> str:
    """Force the psycopg (v3) driver regardless of the URL's declared scheme."""
    return (
        make_url(database_url)
        .set(drivername="postgresql+psycopg")
        .render_as_string(hide_password=False)
    )


engine = create_engine(
    _psycopg_url(get_settings().database_url),
    pool_pre_ping=True,
    # Belt-and-suspenders with pool_pre_ping against Supabase's own
    # connection lifetime limits: a connection that's about to be reused
    # past this age gets replaced instead of risking a stale-connection
    # error. DATABASE_URL points at Supabase's transaction-mode pooler
    # (port 6543, not the 15-connection session-mode pooler on 5432) which
    # multiplexes far more concurrent app connections onto a smaller set of
    # real Postgres backends -- Celery worker concurrency is still capped
    # (see docker-compose.yml/Makefile) as a second line of defense, not
    # because 6543 has the same hard ceiling 5432 did.
    pool_recycle=300,
    # PgBouncer's transaction mode can hand two different app connections
    # the same underlying Postgres backend at different times, without
    # resetting server-side prepared statements between them. psycopg3's
    # default auto-prepare (after ~5 uses of the same statement) then
    # collides with a same-named statement left by a prior connection
    # ("DuplicatePreparedStatement") -- confirmed live under sustained
    # worker load after switching to 6543. Disabling it forces the simple
    # unnamed-statement protocol every time, which is what transaction-mode
    # pooling requires.
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(bind=engine)
