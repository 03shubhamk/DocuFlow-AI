"""
DocuFlow AI — JWT & Password Security.

Provides password hashing with bcrypt, JWT access token management,
and cryptographic refresh token generation and hashing for secure rotation.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import Settings
from app.domain.exceptions import InvalidTokenException, TokenExpiredException


def hash_password(password: str) -> str:
    """Return bcrypt hash of the given password using modern direct bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    pwd_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_secure_random_token() -> str:
    """Generate a cryptographically secure URL-safe random string for refresh tokens."""
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of a raw token string for secure database lookup."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    settings: Settings,
    subject: str,
    tenant_id: str,
    role: str,
    email: str,
) -> tuple[str, datetime]:
    """Create a signed JWT access token.

    Returns:
        Tuple of (encoded_jwt, expiry_datetime).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "exp": expires_at,
        "iat": now,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_token_pair(
    settings: Settings,
    user_id: str,
    tenant_id: str,
    role: str,
    email: str,
) -> tuple[str, str, datetime, datetime]:
    """Create a new access token (JWT) and raw refresh token pair.

    Returns:
        Tuple of (access_token, raw_refresh_token, access_expires_at, refresh_expires_at).
    """
    access_token, access_expires_at = create_access_token(
        settings=settings,
        subject=user_id,
        tenant_id=tenant_id,
        role=role,
        email=email,
    )
    raw_refresh_token = generate_secure_random_token()
    refresh_expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return access_token, raw_refresh_token, access_expires_at, refresh_expires_at


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Returns:
        Decoded token payload dict.

    Raises:
        TokenExpiredException: If the token has expired.
        InvalidTokenException: If the token is malformed or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise InvalidTokenException("Token is not a valid access token.")
        return payload
    except JWTError as e:
        if "expired" in str(e).lower():
            raise TokenExpiredException() from e
        raise InvalidTokenException("Invalid or malformed authentication token.") from e
