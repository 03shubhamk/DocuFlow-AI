"""
DocuFlow AI — Authentication Data Transfer Objects (Pydantic Schemas).

Validates all authentication requests and serializes domain responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Payload for registering a new user account."""

    email: EmailStr = Field(description="User's unique email address")
    password: str = Field(min_length=8, max_length=128, description="User password (min 8 chars)")
    full_name: str = Field(min_length=1, max_length=255, description="Full name of user")
    tenant_name: str | None = Field(
        default=None, description="Optional workspace name for new tenant"
    )
    role: str = Field(default="USER", description="Initial role (USER or ADMIN)")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLoginRequest(BaseModel):
    """Payload for user authentication with email and password."""

    email: EmailStr = Field(description="User's email address")
    password: str = Field(description="User's plaintext password")


class RefreshTokenRequest(BaseModel):
    """Payload for rotating an expired access token using a refresh token."""

    refresh_token: str = Field(
        min_length=10, description="Valid cryptographically signed refresh token"
    )


class TokenResponse(BaseModel):
    """Response returned upon successful login or token refresh."""

    access_token: str = Field(description="Short-lived JWT access token")
    refresh_token: str = Field(description="Rotating refresh token")
    token_type: str = Field(default="bearer", description="Token type header prefix")
    expires_in: int = Field(description="Access token validity duration in seconds")


class UserResponse(BaseModel):
    """Serialized user representation for public responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique User UUID")
    tenant_id: uuid.UUID = Field(description="Assigned Tenant Workspace UUID")
    email: str = Field(description="User email address")
    full_name: str = Field(description="User full name")
    role: str = Field(description="Assigned RBAC role")
    is_active: bool = Field(description="Account active status")
    created_at: datetime = Field(description="Account creation timestamp")


class MessageResponse(BaseModel):
    """Generic status message response."""

    detail: str = Field(description="Status message description")
