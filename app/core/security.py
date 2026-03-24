"""
Security Utilities
==================
Equivalent to Laravel's Hash facade + JWT guard.

Provides:
- Password hashing (bcrypt via passlib)
- JWT access + refresh token creation
- Token decoding and validation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password Hashing ──────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password. Equivalent to Hash::make()."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash. Equivalent to Hash::check()."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Creation ────────────────────────────────────────────────────────
def _create_token(
    subject: str | UUID,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str | UUID, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a short-lived access token.
    Equivalent to JWTAuth::attempt() returning an access token.
    """
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=extra_claims,
    )


def create_refresh_token(user_id: str | UUID) -> str:
    """Create a long-lived refresh token."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ── Token Decoding ────────────────────────────────────────────────────────────
def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises JWTError on invalid/expired tokens.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_token_subject(token: str) -> str:
    """Extract the 'sub' (user ID) from a token."""
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise JWTError("Token has no subject")
    return sub


def get_token_type(token: str) -> str:
    """Extract the token type ('access' or 'refresh')."""
    payload = decode_token(token)
    return payload.get("type", "")
