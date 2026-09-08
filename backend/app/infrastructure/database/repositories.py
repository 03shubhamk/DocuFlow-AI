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
    DocumentAssetModel,
    DocumentModel,
    DocumentVersionModel,
    ProcessingJobModel,
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

    async def create(
        self,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID,
        title: str,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        storage_path: str,
        checksum_sha256: str,
        id: uuid.UUID | None = None,
    ) -> DocumentModel:
        doc = DocumentModel(
            id=id or uuid.uuid4(),
            tenant_id=tenant_id,
            owner_id=owner_id,
            title=title,
            original_filename=original_filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            storage_path=storage_path,
            checksum_sha256=checksum_sha256,
            is_deleted=False,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc


    async def get_by_id(self, document_id: uuid.UUID) -> DocumentModel | None:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_checksum(self, tenant_id: uuid.UUID, checksum_sha256: str) -> DocumentModel | None:
        """Find non-deleted document with matching checksum in the same tenant."""
        stmt = select(DocumentModel).where(
            DocumentModel.tenant_id == tenant_id,
            DocumentModel.checksum_sha256 == checksum_sha256,
            DocumentModel.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_scoped(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
        include_deleted: bool = False,
    ) -> DocumentModel | None:
        """Fetch document scoped to tenant and optionally owner (for non-admin users)."""
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.tenant_id == tenant_id,
        )
        if not include_deleted:
            stmt = stmt.where(DocumentModel.is_deleted.is_(False))
        if owner_id is not None:
            stmt = stmt.where(DocumentModel.owner_id == owner_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> DocumentModel | None:
        """Fetch document with versions, assets, and jobs loaded."""
        from sqlalchemy.orm import selectinload

        stmt = (
            select(DocumentModel)
            .options(
                selectinload(DocumentModel.versions),
                selectinload(DocumentModel.assets),
                selectinload(DocumentModel.jobs),
            )
            .where(
                DocumentModel.id == document_id,
                DocumentModel.tenant_id == tenant_id,
                DocumentModel.is_deleted.is_(False),
            )
        )
        if owner_id is not None:
            stmt = stmt.where(DocumentModel.owner_id == owner_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
        file_type: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[DocumentModel], int]:
        """List documents with tenant/owner isolation, filtering, search, sorting, and pagination."""
        from sqlalchemy import asc, desc, func

        query = select(DocumentModel).where(
            DocumentModel.tenant_id == tenant_id,
            DocumentModel.is_deleted.is_(False),
        )

        if owner_id is not None:
            query = query.where(DocumentModel.owner_id == owner_id)

        if file_type:
            ft = file_type.lower()
            if not ft.startswith("."):
                ft = f".{ft}"
            query = query.where(func.lower(DocumentModel.file_type) == ft)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                DocumentModel.title.ilike(search_pattern)
                | DocumentModel.original_filename.ilike(search_pattern)
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_stmt)
        total_items = total_result.scalar_one()

        # Sorting
        sort_col = getattr(DocumentModel, sort_by, DocumentModel.created_at)
        query = query.order_by(desc(sort_col) if order.lower() == "desc" else asc(sort_col))

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total_items

    async def soft_delete(self, document_id: uuid.UUID) -> None:
        """Mark document as deleted."""
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(is_deleted=True, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()


class DocumentVersionRepository:
    """Repository for DocumentVersion snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: uuid.UUID,
        version_number: int,
        storage_path: str,
        file_size_bytes: int,
        checksum_sha256: str,
    ) -> DocumentVersionModel:
        version = DocumentVersionModel(
            document_id=document_id,
            version_number=version_number,
            storage_path=storage_path,
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
        )
        self.session.add(version)
        await self.session.flush()
        return version


class DocumentAssetRepository:
    """Repository for Document secondary assets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        asset_type: str,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
        asset_metadata: dict[str, Any] | None = None,
    ) -> DocumentAssetModel:
        asset = DocumentAssetModel(
            document_id=document_id,
            version_id=version_id,
            asset_type=asset_type,
            storage_path=storage_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            asset_metadata=asset_metadata or {},
        )
        self.session.add(asset)
        await self.session.flush()
        return asset


class ProcessingJobRepository:
    """Repository for asynchronous ProcessingJob state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        status: str = "UPLOADED",
        stage: str = "INGESTION",
        progress_percent: int = 0,
        celery_task_id: str | None = None,
    ) -> ProcessingJobModel:
        job = ProcessingJobModel(
            document_id=document_id,
            version_id=version_id,
            status=status,
            stage=stage,
            progress_percent=progress_percent,
            celery_task_id=celery_task_id,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> ProcessingJobModel | None:
        stmt = select(ProcessingJobModel).where(ProcessingJobModel.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_document(self, document_id: uuid.UUID) -> ProcessingJobModel | None:
        from sqlalchemy import desc

        stmt = (
            select(ProcessingJobModel)
            .where(ProcessingJobModel.document_id == document_id)
            .order_by(desc(ProcessingJobModel.created_at))
            .limit(1)
        )
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

