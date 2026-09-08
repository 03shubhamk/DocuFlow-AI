"""
DocuFlow AI — FastAPI Dependency Injection Providers.

Provides reusable Depends() factories for:
- Database sessions
- Application Settings
- Authenticated user identity (JWT)
- Role-Based Access Control (RBAC)
- Document ownership and tenant isolation
"""

from __future__ import annotations

import uuid
from typing import Annotated, AsyncGenerator, Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain.entities import UserRole
from app.domain.exceptions import (
    ForbiddenException,
    InvalidTokenException,
    UnauthorizedException,
)
from app.infrastructure.database.models import DocumentModel, UserModel
from app.infrastructure.database.repositories import UserRepository
from app.infrastructure.database.session import build_engine, build_session_factory
from app.infrastructure.security.tokens import decode_access_token
from app.infrastructure.storage import ObjectStorage, get_storage

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)

# Cached engine and session factory
_engine = None
_session_factory = None


def get_settings_dep() -> Settings:
    """Dependency: return validated application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_storage_dep() -> ObjectStorage:
    """Dependency: return configured ObjectStorage backend."""
    return get_storage()


StorageDep = Annotated[ObjectStorage, Depends(get_storage_dep)]



async def get_db(settings: SettingsDep) -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session per request."""
    global _engine, _session_factory
    if _engine is None:
        _engine = build_engine(settings)
        _session_factory = build_session_factory(_engine)

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DbSession,
    settings: SettingsDep,
) -> UserModel:
    """Extract and validate the current authenticated user from the Bearer JWT token."""
    if not token:
        raise UnauthorizedException("Missing authentication token.")

    payload = decode_access_token(settings, token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenException("Token payload missing subject.")

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError) as e:
        raise InvalidTokenException("Malformed user identifier in token.") from e

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise UnauthorizedException("User account no longer exists.")

    if not user.is_active:
        raise UnauthorizedException("User account is inactive.")

    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole | str) -> Callable[..., UserModel]:
    """Dependency factory restricting route access to specified roles."""
    role_values = {r.value if isinstance(r, UserRole) else str(r).upper() for r in allowed_roles}

    def role_checker(current_user: CurrentUser) -> UserModel:
        if current_user.role not in role_values:
            raise ForbiddenException(
                f"Requires one of roles: {', '.join(sorted(role_values))}. Current role: '{current_user.role}'."
            )
        return current_user

    return role_checker


AdminUser = Annotated[UserModel, Depends(require_role(UserRole.ADMIN))]


def check_document_access(document: DocumentModel, current_user: UserModel) -> None:
    """Enforces multi-tenant and account/user document isolation.

    Raises ForbiddenException if user cannot access the document.
    """
    if document.tenant_id != current_user.tenant_id:
        raise ForbiddenException("Document belongs to a different organization.")

    if current_user.role == UserRole.ADMIN.value:
        return

    if document.owner_id != current_user.id:
        raise ForbiddenException("You do not have permission to access another user's document.")
