from __future__ import annotations

import hashlib
import hmac
import secrets


TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def compare_tokens(plaintext: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(plaintext), stored_hash)
