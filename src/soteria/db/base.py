"""SQLAlchemy declarative base.

Table models (src/soteria/db/models/*.py) are deferred to a later pass;
this only provides the shared base class they'll eventually inherit from.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
