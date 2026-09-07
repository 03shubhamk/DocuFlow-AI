"""
DocuFlow AI — JWT & Password Security.

Provides password hashing with bcrypt and JWT access/refresh token management.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import Settings
from app.domain.exceptions import InvalidCredentialsException, TokenExpiredException

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return bcrypt hash of the given password."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


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
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Returns:
        Decoded token payload dict.

    Raises:
        TokenExpiredException: If the token has expired.
        InvalidCredentialsException: If the token is malformed or invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise InvalidCredentialsException()
        return payload
    except JWTError as e:
        if "expired" in str(e).lower():
            raise TokenExpiredException() from e
        raise InvalidCredentialsException() from e
