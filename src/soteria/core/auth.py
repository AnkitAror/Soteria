"""Supabase Auth JWT verification and current-user resolution.

The frontend authenticates directly against Supabase Auth (email/password,
OAuth, etc.) and sends the resulting access token as a Bearer header on
every request to this API — we never see credentials, only verify the
token's signature and trust its claims. Verification is against the
project's public JWKS (asymmetric signing keys), not a shared secret:
newer Supabase projects don't expose a plain HS256 secret at all.

`users.id` is set equal to the Supabase Auth user's `sub` claim, so no
separate id-mapping table is needed. The first request from a new Supabase
user provisions their `users` row.
"""

import uuid
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from soteria.core.config import get_settings
from soteria.db.models.users import User
from soteria.db.session import SessionLocal

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client() -> PyJWKClient:
    jwks_url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
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
