"""ORM models, one module per table in references/db_schema.md.

Importing this package registers all model classes on Base.metadata,
which alembic/env.py depends on for autogenerate.
"""

from soteria.db.models import (
    bank_accounts,
    chat_messages,
    chat_sessions,
    embeddings,
    insights,
    merchant_profiles,
    plaid_items,
    subscriptions,
    transaction_analysis,
    transactions,
    users,
)
