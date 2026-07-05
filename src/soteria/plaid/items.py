"""Persist exchanged Plaid Items to the database.

No real user/auth system exists yet, so every item created here is attached
to a single fixed dev user — get-or-create'd on first use. Replace with real
user attribution once auth lands.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from soteria.core.security import decrypt_secret, encrypt_secret
from soteria.db.models.plaid_items import PlaidItem
from soteria.db.models.users import User
from soteria.db.session import SessionLocal

DEV_USER_EMAIL = "dev@soteria.local"


def _get_or_create_dev_user(session: Session) -> User:
    user = session.query(User).filter_by(email=DEV_USER_EMAIL).one_or_none()
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        session.add(user)
        session.flush()
    return user


def save_plaid_item(
    *,
    item_id: str,
    access_token: str,
    institution_id: str,
    institution_name: str,
) -> PlaidItem:
    with SessionLocal() as session:
        user = _get_or_create_dev_user(session)
        plaid_item = PlaidItem(
            user_id=user.id,
            plaid_item_id=item_id,
            plaid_access_token=encrypt_secret(access_token),
            institution_id=institution_id,
            institution_name=institution_name,
        )
        session.add(plaid_item)
        session.commit()
        session.refresh(plaid_item)
        return plaid_item


def get_plaid_item(plaid_item_id: str) -> PlaidItem:
    with SessionLocal() as session:
        plaid_item = session.get(PlaidItem, uuid.UUID(plaid_item_id))
        if plaid_item is None:
            raise ValueError(f"No PlaidItem with id {plaid_item_id}")
        return plaid_item


def get_decrypted_access_token(plaid_item: PlaidItem) -> str:
    return decrypt_secret(plaid_item.plaid_access_token)


def update_sync_cursor(plaid_item_id: uuid.UUID, cursor: str) -> None:
    with SessionLocal() as session:
        plaid_item = session.get(PlaidItem, plaid_item_id)
        if plaid_item is None:
            raise ValueError(f"No PlaidItem with id {plaid_item_id}")
        plaid_item.sync_cursor = cursor
        plaid_item.last_synced_at = datetime.now(UTC)
        session.commit()
