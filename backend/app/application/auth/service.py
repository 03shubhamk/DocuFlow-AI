"""
DocuFlow AI — Authentication Application Service.

Encapsulates user registration, credential verification, JWT token issuance,
secure refresh token rotation, and session invalidation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.config import Settings
from app.domain.entities import UserRole
from app.domain.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
    UserAlreadyExistsException,
)
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.repositories import (
    AuditLogRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from app.infrastructure.security.tokens import (
    create_token_pair,
    hash_password,
    hash_token,
    verify_password,
)


class AuthService:
    """Service handling all authentication workflows."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.user_repo = UserRepository(session)
        self.tenant_repo = TenantRepository(session)
        self.token_repo = RefreshTokenRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def register(self, request: UserRegisterRequest) -> UserResponse:
        """Register a new user, assign to tenant workspace, and hash credentials."""
        existing = await self.user_repo.get_by_email(request.email)
        if existing:
            raise UserAlreadyExistsException(request.email)

        # Determine tenant workspace
        if request.tenant_name:
            tenant = await self.tenant_repo.create(name=request.tenant_name)
        else:
            tenant = await self.tenant_repo.get_or_create_default()

        # Normalize role
        role_str = request.role.upper().strip()
        role = UserRole.ADMIN.value if role_str == UserRole.ADMIN.value else UserRole.USER.value

        hashed_pwd = hash_password(request.password)

        user = await self.user_repo.create(
            tenant_id=tenant.id,
            email=request.email,
            hashed_password=hashed_pwd,
            full_name=request.full_name,
            role=role,
            is_active=True,
        )

        await self.audit_repo.log_action(
            tenant_id=tenant.id,
            user_id=user.id,
            action="USER_REGISTER",
            resource_type="USER",
            resource_id=user.id,
            details={"email": user.email, "role": user.role},
        )

        return UserResponse.model_validate(user)

    async def login(
        self,
        request: UserLoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticate user credentials and issue an access + refresh token pair."""
        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise InvalidCredentialsException()

        if not user.is_active:
            raise InvalidCredentialsException()

        # Issue dual-token pair
        access_token, raw_refresh, access_exp, refresh_exp = create_token_pair(
            settings=self.settings,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
        )

        # Store refresh token hash for rotation & revocation tracking
        token_hash = hash_token(raw_refresh)
        await self.token_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_exp,
        )

        await self.audit_repo.log_action(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="USER_LOGIN",
            resource_type="SESSION",
            resource_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": user.email},
        )

        expires_in = int((access_exp - datetime.now(timezone.utc)).total_seconds())

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def refresh_token(self, raw_refresh_token: str) -> TokenResponse:
        """Rotate an active refresh token: revoke the old token and issue a fresh pair."""
        token_hash = hash_token(raw_refresh_token)
        token_record = await self.token_repo.get_by_token_hash(token_hash)

        if not token_record or token_record.revoked_at is not None:
            raise InvalidTokenException("Refresh token is invalid or has been revoked.")

        now = datetime.now(timezone.utc)
        expires_at = (
            token_record.expires_at.replace(tzinfo=timezone.utc)
            if token_record.expires_at.tzinfo is None
            else token_record.expires_at
        )
        if expires_at <= now:
            raise TokenExpiredException()

        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise InvalidCredentialsException()

        # 1. Revoke the used refresh token (strict token rotation)
        await self.token_repo.revoke(token_record)

        # 2. Issue new token pair
        access_token, new_raw_refresh, access_exp, refresh_exp = create_token_pair(
            settings=self.settings,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
        )

        # 3. Store new refresh token hash
        new_token_hash = hash_token(new_raw_refresh)
        await self.token_repo.create(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=refresh_exp,
        )

        expires_in = int((access_exp - datetime.now(timezone.utc)).total_seconds())

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def logout(self, user: UserModel, raw_refresh_token: str | None = None) -> None:
        """Invalidate the refresh token session upon logout."""
        if raw_refresh_token:
            token_hash = hash_token(raw_refresh_token)
            token_record = await self.token_repo.get_by_token_hash(token_hash)
            if token_record and token_record.user_id == user.id:
                await self.token_repo.revoke(token_record)
        else:
            # Revoke all active sessions for this user
            await self.token_repo.revoke_all_for_user(user.id)

        await self.audit_repo.log_action(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action="USER_LOGOUT",
            resource_type="SESSION",
            resource_id=user.id,
        )
