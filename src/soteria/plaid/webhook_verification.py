"""Verify that an incoming webhook was really sent by Plaid.

Plaid signs each webhook with a JWT (ES256) in the `Plaid-Verification`
header. Verification, per Plaid's documented process:
  1. Read the unverified JWT header to get the signing key's `kid`.
  2. Fetch that key from Plaid (cached in-process by kid; keys rotate rarely).
  3. Reject if the key has been retired (`expired_at` set).
  4. Verify the JWT signature with that key (ES256).
  5. Reject if `iat` is more than 5 minutes old (replay protection).
  6. Reject if the JWT's `request_body_sha256` doesn't match the actual body.
"""

import hashlib
import time

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from jwt.algorithms import ECAlgorithm
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

from soteria.plaid.client import plaid_client

_MAX_IAT_AGE_SECONDS = 5 * 60

_key_cache: dict[str, dict] = {}


def _get_verification_key(key_id: str) -> dict:
    if key_id not in _key_cache:
        request = WebhookVerificationKeyGetRequest(key_id=key_id)
        response = plaid_client.webhook_verification_key_get(request)
        _key_cache[key_id] = response.key.to_dict()
    return _key_cache[key_id]


def is_webhook_authentic(body: bytes, signed_jwt: str) -> bool:
    try:
        header = jwt.get_unverified_header(signed_jwt)
    except jwt.InvalidTokenError:
        return False

    key_id = header.get("kid")
    if not key_id:
        return False

    key = _get_verification_key(key_id)
    if key.get("expired_at") is not None:
        return False

    public_key = ECAlgorithm.from_jwk(key)
    if not isinstance(public_key, EllipticCurvePublicKey):
        return False
    try:
        payload = jwt.decode(signed_jwt, key=public_key, algorithms=["ES256"])
    except jwt.InvalidTokenError:
        return False

    if time.time() - payload.get("iat", 0) > _MAX_IAT_AGE_SECONDS:
        return False

    expected_hash = hashlib.sha256(body).hexdigest()
    return expected_hash == payload.get("request_body_sha256")
