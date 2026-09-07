"""
DocuFlow AI — Database Repositories.

Provides async CRUD operations and query abstractions for domain models
using SQLAlchemy 2.0 select statements.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    AuditLogModel,
    DocumentModel,
    RefreshTokenModel,
    TenantModel,
    UserModel,
)


class TenantRepository:
    """Repository for Tenant organizational workspaces."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, tenant_id: uuid.UUID) -> TenantModel | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> TenantModel | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, slug: str | None = None) -> TenantModel:
        if not slug:
            slug = name.lower().replace(" ", "-").replace("_", "-")[:100]
            # Ensure slug uniqueness
            existing = await self.get_by_slug(slug)
            if existing:
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        tenant = TenantModel(name=name, slug=slug, is_active=True)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def get_or_create_default(
        self, name: str = "Default Workspace", slug: str = "default"
    ) -> TenantModel:
        tenant = await self.get_by_slug(slug)
        if not tenant:
            tenant = TenantModel(name=name, slug=slug, is_active=True)
            self.session.add(tenant)
            await self.session.flush()
        return tenant


class UserRepository:
    """Repository for User identity and account records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(
        self, email: str, tenant_id: uuid.UUID | None = None
    ) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email.lower().strip())
        if tenant_id is not None:
            stmt = stmt.where(UserModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant_id: uuid.UUID,
        email: str,
        hashed_password: str,
        full_name: str,
        role: str = "USER",
        is_active: bool = True,
    ) -> UserModel:
        user = UserModel(
            tenant_id=tenant_id,
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        self.session.add(user)
        await self.session.flush()
        return user


class RefreshTokenRepository:
    """Repository for managing rotating refresh tokens and revocation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshTokenModel:
        refresh_token = RefreshTokenModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_by_token_hash(self, token_hash: str) -> RefreshTokenModel | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, token_model: RefreshTokenModel) -> None:
        token_model.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()


class DocumentRepository:
    """Repository for Document records with tenant and user isolation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, document_id: uuid.UUID) -> DocumentModel | None:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_scoped(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> DocumentModel | None:
        """Fetch document scoped to tenant and optionally owner (for non-admin users)."""
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.tenant_id == tenant_id,
            DocumentModel.is_deleted.is_(False),
        )
        if owner_id is not None:
            stmt = stmt.where(DocumentModel.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AuditLogRepository:
    """Repository for system audit trail logging."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_action(
        self,
        tenant_id: uuid.UUID,
        action: str,
        resource_type: str,
        user_id: uuid.UUID | None = None,
        resource_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLogModel:
        audit = AuditLogModel(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        self.session.add(audit)
        await self.session.flush()
        return audit
