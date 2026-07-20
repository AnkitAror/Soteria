"""Supabase Auth JWT verification and current-user resolution.

The frontend authenticates directly against Supabase Auth (email/password,
OAuth, etc.) and sends the resulting access token as a Bearer header on
every request to this API — we never see credentials, only verify the
token's signature against the project's JWT secret and trust its claims.

`users.id` is set equal to the Supabase Auth user's `sub` claim, so no
separate id-mapping table is needed. The first request from a new Supabase
user provisions their `users` row.
"""

import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from soteria.core.config import get_settings
from soteria.db.models.users import User
from soteria.db.session import SessionLocal

_bearer_scheme = HTTPBearer(auto_error=False)


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            get_settings().supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


def _get_or_create_user(session: Session, user_id: uuid.UUID, email: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=email)
        session.add(user)
        session.flush()
    return user


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> uuid.UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials"
        )

    claims = _decode_supabase_jwt(credentials.credentials)
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing sub/email"
        )

    user_id = uuid.UUID(sub)
    with SessionLocal() as session:
        user = _get_or_create_user(session, user_id, email)
        session.commit()
        return user.id


def get_current_user(user_id: uuid.UUID = Depends(get_current_user_id)) -> User:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        session.expunge(user)
        return user
