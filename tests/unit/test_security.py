"""Unit tests for app-layer secret encryption."""

from soteria.core.security import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "access-sandbox-fake-token"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext
