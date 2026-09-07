"""
DocuFlow AI — Authentication API Endpoints.

Provides:
- POST /api/v1/auth/register — User account creation
- POST /api/v1/auth/login    — Credential verification & token pair issuance
- POST /api/v1/auth/refresh  — Secure refresh token rotation
- POST /api/v1/auth/logout   — Session revocation
- GET  /api/v1/auth/me       — Current authenticated user profile
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUser, DbSession, SettingsDep
from app.application.auth.schemas import (
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.application.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    request: UserRegisterRequest,
    db: DbSession,
    settings: SettingsDep,
) -> UserResponse:
    """Create a new user account, hash the password, and assign to a workspace."""
    auth_service = AuthService(db, settings)
    return await auth_service.register(request)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue token pair",
)
async def login(
    request_data: UserLoginRequest,
    http_request: Request,
    db: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    """Validate user credentials and return an access token + rotating refresh token."""
    auth_service = AuthService(db, settings)
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    return await auth_service.login(
        request=request_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token for new credentials",
)
async def refresh(
    request: RefreshTokenRequest,
    db: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    """Exchange a valid refresh token for a newly rotated access token + refresh token pair."""
    auth_service = AuthService(db, settings)
    return await auth_service.refresh_token(request.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke session refresh token",
)
async def logout(
    current_user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    request: RefreshTokenRequest | None = None,
) -> MessageResponse:
    """Revoke active refresh token session for the current user."""
    auth_service = AuthService(db, settings)
    raw_token = request.refresh_token if request else None
    await auth_service.logout(user=current_user, raw_refresh_token=raw_token)
    return MessageResponse(detail="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the profile information of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
