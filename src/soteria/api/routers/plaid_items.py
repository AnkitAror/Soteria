"""Account management endpoints: list connected institutions, relink an
expired one via Plaid update-mode Link, or unlink one entirely.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from soteria.core.auth import get_current_user_id
from soteria.db.models.bank_accounts import BankAccount
from soteria.db.models.plaid_items import PlaidItem
from soteria.db.session import SessionLocal
from soteria.plaid.items import (
    get_decrypted_access_token,
    list_plaid_items_for_user,
    mark_item_active,
    remove_plaid_item,
)
from soteria.plaid.link import create_link_token

router = APIRouter(prefix="/api", tags=["account-management"])


class InstitutionSummary(BaseModel):
    id: str
    institution_name: str
    status: str
    error_code: str | None
    account_count: int
    last_synced_at: str | None


class InstitutionsResponse(BaseModel):
    institutions: list[InstitutionSummary]


class LinkTokenResponse(BaseModel):
    link_token: str


def _get_owned_item(session: Session, plaid_item_id: uuid.UUID, user_id: uuid.UUID) -> PlaidItem:
    plaid_item = session.get(PlaidItem, plaid_item_id)
    if plaid_item is None or plaid_item.user_id != user_id:
        raise HTTPException(status_code=404, detail="Institution not found")
    return plaid_item


@router.get("/institutions")
def list_institutions(user_id: uuid.UUID = Depends(get_current_user_id)) -> InstitutionsResponse:
    plaid_items = list_plaid_items_for_user(user_id)

    with SessionLocal() as session:
        count_rows = (
            session.query(BankAccount.plaid_item_id, func.count(BankAccount.id))
            .filter(BankAccount.user_id == user_id, BankAccount.deleted_at.is_(None))
            .group_by(BankAccount.plaid_item_id)
            .all()
        )
        counts: dict[uuid.UUID, int] = {row[0]: row[1] for row in count_rows}

    return InstitutionsResponse(
        institutions=[
            InstitutionSummary(
                id=str(item.id),
                institution_name=item.institution_name,
                status=item.status.value,
                error_code=item.error_code,
                account_count=counts.get(item.id, 0),
                last_synced_at=item.last_synced_at.isoformat() if item.last_synced_at else None,
            )
            for item in plaid_items
        ]
    )


@router.post("/institutions/{plaid_item_id}/relink-token")
def relink_token(
    plaid_item_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> LinkTokenResponse:
    with SessionLocal() as session:
        plaid_item = _get_owned_item(session, plaid_item_id, user_id)
        access_token = get_decrypted_access_token(plaid_item)

    return LinkTokenResponse(link_token=create_link_token(user_id, access_token=access_token))


@router.post("/institutions/{plaid_item_id}/relink-complete", status_code=204)
def relink_complete(
    plaid_item_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> None:
    with SessionLocal() as session:
        _get_owned_item(session, plaid_item_id, user_id)
    mark_item_active(plaid_item_id)


@router.delete("/institutions/{plaid_item_id}", status_code=204)
def unlink_institution(
    plaid_item_id: uuid.UUID, user_id: uuid.UUID = Depends(get_current_user_id)
) -> None:
    with SessionLocal() as session:
        _get_owned_item(session, plaid_item_id, user_id)
    remove_plaid_item(plaid_item_id)
