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


engine = create_engine(_psycopg_url(get_settings().database_url), pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine)
