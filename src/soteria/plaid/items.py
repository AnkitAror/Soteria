"""Persist exchanged Plaid Items to the database."""

import uuid
from datetime import UTC, datetime

from plaid.model.item_remove_request import ItemRemoveRequest

from soteria.core.security import decrypt_secret, encrypt_secret
from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.plaid_items import PlaidItem, PlaidItemStatus
from soteria.db.session import SessionLocal
from soteria.plaid.client import plaid_client


def save_plaid_item(
    *,
    user_id: uuid.UUID,
    item_id: str,
    access_token: str,
    institution_id: str,
    institution_name: str,
) -> PlaidItem:
    with SessionLocal() as session:
        plaid_item = PlaidItem(
            user_id=user_id,
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


def get_plaid_item_by_item_id(item_id: str) -> PlaidItem | None:
    """Look up by Plaid's own item_id string (as delivered in webhooks), not our internal id."""
    with SessionLocal() as session:
        return session.query(PlaidItem).filter_by(plaid_item_id=item_id).one_or_none()


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


def list_plaid_items_for_user(user_id: uuid.UUID) -> list[PlaidItem]:
    with SessionLocal() as session:
        return (
            session.query(PlaidItem)
            .filter(PlaidItem.user_id == user_id, PlaidItem.status != PlaidItemStatus.REVOKED)
            .order_by(PlaidItem.institution_name)
            .all()
        )


def mark_item_login_required(item_id: str, error_code: str | None) -> None:
    """item_id is Plaid's own item_id (as delivered in webhooks), not our internal id."""
    with SessionLocal() as session:
        plaid_item = session.query(PlaidItem).filter_by(plaid_item_id=item_id).one_or_none()
        if plaid_item is None:
            return
        plaid_item.status = PlaidItemStatus.LOGIN_REQUIRED
        plaid_item.error_code = error_code
        session.commit()


def mark_item_active(plaid_item_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        plaid_item = session.get(PlaidItem, plaid_item_id)
        if plaid_item is None:
            raise ValueError(f"No PlaidItem with id {plaid_item_id}")
        plaid_item.status = PlaidItemStatus.ACTIVE
        plaid_item.error_code = None
        session.commit()


def remove_plaid_item(plaid_item_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        plaid_item = session.get(PlaidItem, plaid_item_id)
        if plaid_item is None:
            raise ValueError(f"No PlaidItem with id {plaid_item_id}")

        access_token = decrypt_secret(plaid_item.plaid_access_token)
        plaid_client.item_remove(ItemRemoveRequest(access_token=access_token))

        plaid_item.status = PlaidItemStatus.REVOKED
        now = datetime.now(UTC)
        session.query(BankAccount).filter(
            BankAccount.plaid_item_id == plaid_item_id, BankAccount.deleted_at.is_(None)
        ).update({BankAccount.deleted_at: now})
        session.commit()
