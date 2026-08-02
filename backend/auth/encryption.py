# backend/auth/encryption.py
#
# Fernet symmetric encryption for storing GitHub OAuth tokens at rest.
# Tokens are encrypted before DB insert and decrypted on read.

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the JWT secret (any-length string)."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plaintext: str, secret: str) -> str:
    """Encrypt a plaintext token using the app's JWT secret."""
    key = _derive_fernet_key(secret)
    f = Fernet(key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str, secret: str) -> str:
    """Decrypt an encrypted token using the app's JWT secret."""
    key = _derive_fernet_key(secret)
    f = Fernet(key)
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("decrypt_token | failed — invalid key or corrupted ciphertext")
        raise ValueError("Cannot decrypt token — key mismatch or data corruption")
