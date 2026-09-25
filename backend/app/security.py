"""
Authentication primitives (Phase 2).

* Passwords: bcrypt with a per-user salt. The legacy
  ``sha256(password + static_salt)`` scheme from Version 1 is still verifiable so
  existing accounts keep working, but the stored hash is transparently upgraded
  to bcrypt on the next successful login.
* Tokens: signed JWT (HS256) carrying the user id. The API no longer needs to
  trust a client supplied ``X-User-Id`` header.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("security")

# Version-1 scheme (kept only for verification + migration)
LEGACY_SALT = "smartfarm_secret_salt_123"
LEGACY_PREFIX = "sha256$"


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with bcrypt (per-user random salt)."""
    if not isinstance(password, str) or password == "":
        raise ValueError("password must be a non-empty string")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def legacy_hash_password(password: str) -> str:
    """Reproduce the Version-1 hash (verification / migration tests only)."""
    return hashlib.sha256((password + LEGACY_SALT).encode("utf-8")).hexdigest()


def is_legacy_hash(stored: str) -> bool:
    """A bare 64-char hex digest is a Version-1 record."""
    if not stored:
        return False
    if stored.startswith(LEGACY_PREFIX) or stored.startswith("$2"):
        return False
    return len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower())


def verify_password(password: str, stored: str) -> bool:
    """Verify against a bcrypt hash or a legacy sha256 hash."""
    if not password or not stored:
        return False
    if is_legacy_hash(stored):
        return hashlib.sha256((password + LEGACY_SALT).encode("utf-8")).hexdigest() == stored.lower()
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def needs_rehash(stored: str) -> bool:
    return is_legacy_hash(stored)


# --------------------------------------------------------------------------
# JWT access tokens
# --------------------------------------------------------------------------
def create_access_token(user_id: int, email: str, name: str = "", expires_minutes: Optional[int] = None) -> str:
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "iss": "smartfarm-adis",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Return the payload, or None when the token is invalid/expired."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="smartfarm-adis",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        logger.info("Rejected expired access token")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Rejected invalid access token: %s", exc)
        return None


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract the raw token from an ``Authorization: Bearer <t>`` header."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def validate_password_strength(password: str) -> Optional[str]:
    """Return an error message when the password is unacceptable, else None."""
    if not isinstance(password, str):
        return "Password must be a string."
    if len(password) < settings.password_min_length:
        return f"Password must be at least {settings.password_min_length} characters long."
    if password.strip() == "":
        return "Password cannot be blank."
    if settings.is_production and password.isdigit():
        return "Password must not be a numeric-only value."
    return None
