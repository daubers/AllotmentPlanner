"""Symmetric encryption for third-party secrets kept in the database (e.g. Mastodon tokens)."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet() -> Fernet:
    secret = current_app.config.get("TOKEN_ENCRYPTION_KEY") or current_app.config["JWT_SECRET_KEY"]
    key = hashlib.sha256(f"allotment-token-encryption:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Raises ``ValueError`` if the key has changed since the value was stored."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Stored secret can't be decrypted (was the encryption key changed?)"
        ) from exc
