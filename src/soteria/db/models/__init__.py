"""ORM models, one module per table in references/db_schema.md.

Importing this package registers all in-scope model classes on Base.metadata,
which alembic/env.py depends on for autogenerate. Only the 4 tables
implemented so far are imported; the remaining 7 stay unimplemented.
"""

from soteria.db.models import bank_accounts, plaid_items, transactions, users
