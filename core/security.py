"""Security primitives: password hashing, signing, CSRF tokens.

Password hashing uses PBKDF2-HMAC-SHA256 with a per-user random salt, the same
algorithm family as Django's default PBKDF2PasswordHasher.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

import settings

_ALGO = "pbkdf2_sha256"


# --- Password hashing -------------------------------------------------------
def hash_password(raw_password: str, *, iterations: int | None = None) -> str:
    """Return an encoded hash string:  pbkdf2_sha256$<iter>$<salt>$<hash>."""
    if not raw_password:
        raise ValueError("Password must not be empty")
    iterations = iterations or settings.PBKDF2_ITERATIONS
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    b64 = base64.b64encode(dk).decode("ascii").strip()
    return f"{_ALGO}${iterations}${salt}${b64}"


def verify_password(raw_password: str, encoded: str) -> bool:
    """Constant-time verification of a raw password against an encoded hash."""
    try:
        algo, iter_s, salt, _b64 = encoded.split("$", 3)
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    try:
        iterations = int(iter_s)
    except ValueError:
        return False
    expected = hash_password_with(raw_password, salt, iterations)
    return hmac.compare_digest(expected, encoded)


def hash_password_with(raw_password: str, salt: str, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    b64 = base64.b64encode(dk).decode("ascii").strip()
    return f"{_ALGO}${iterations}${salt}${b64}"


# --- HMAC signing (used by sessions & CSRF) ---------------------------------
def _key() -> bytes:
    return settings.SECRET_KEY.encode("utf-8")


def sign(value: str) -> str:
    """Return 'value.signature' using HMAC-SHA256."""
    sig = hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"


def unsign(signed_value: str) -> str | None:
    """Return the original value if the signature verifies, else None."""
    try:
        value, sig = signed_value.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    expected = hmac.new(_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, sig):
        return value
    return None


# --- CSRF -------------------------------------------------------------------
def new_csrf_token() -> str:
    """A signed, timestamped random token."""
    raw = f"{secrets.token_hex(16)}:{int(time.time())}"
    return sign(raw)


def csrf_token_valid(token: str, *, max_age: int = 60 * 60 * 12) -> bool:
    raw = unsign(token or "")
    if raw is None:
        return False
    try:
        _rand, ts = raw.split(":", 1)
        issued = int(ts)
    except ValueError:
        return False
    return (time.time() - issued) <= max_age
