from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time


PBKDF2_ITERATIONS = 260_000


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw.encode("ascii"))
        expected = base64.b64decode(digest_raw.encode("ascii"))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def verify_totp(code: str, secret: str, *, now: int | None = None, window: int = 1) -> bool:
    normalized_code = "".join(ch for ch in code if ch.isdigit())
    if len(normalized_code) != 6:
        return False
    now = int(time.time()) if now is None else now
    for offset in range(-window, window + 1):
        if hmac.compare_digest(normalized_code, _totp(secret, now + offset * 30)):
            return True
    return False


def _totp(secret: str, now: int) -> str:
    key = _decode_secret(secret)
    counter = int(now // 30).to_bytes(8, "big")
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def _decode_secret(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        return base64.b32decode((normalized + padding).encode("ascii"), casefold=True)
    except Exception:
        return secret.encode("utf-8")
