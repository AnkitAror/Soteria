"""App-layer encryption helpers for at-rest secrets (e.g. plaid_access_token)."""

from functools import lru_cache

from cryptography.fernet import Fernet

from soteria.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
