"""
DocuFlow AI — Document Application Service.

Orchestrates document upload, validation, storage persistence,
relational database transaction, audit logging, and async queue dispatch.
"""

from __future__ import annotations

import math
import uuid
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.documents.schemas import (
    DocumentAssetSummary,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMessageResponse,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentVersionSummary,
    PaginationMetadata,
    ProcessingJobSummary,
)
from app.application.documents.validation import (
    generate_storage_path,
    process_and_validate_upload_stream,
)
from app.config import get_settings
from app.domain.entities import User, UserRole
from app.domain.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
)
from app.infrastructure.database.repositories import (
    AuditLogRepository,
    DocumentAssetRepository,
    DocumentRepository,
    DocumentVersionRepository,
    ProcessingJobRepository,
)
from app.infrastructure.storage.base import ObjectStorage


class DocumentService:
    """Service layer managing document lifecycle, multi-tenant isolation, and background dispatch."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
    ) -> None:
        self.session = session
        self.storage = storage
        self.document_repo = DocumentRepository(session)
        self.version_repo = DocumentVersionRepository(session)
        self.asset_repo = DocumentAssetRepository(session)
        self.job_repo = ProcessingJobRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.settings = get_settings()

    async def upload_document(
        self,
        file_stream: BinaryIO,
        raw_filename: str,
        content_type: str | None,
        current_user: User,
        title: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> DocumentUploadResponse:
        """Process, validate, store and register a new document."""
        # 1. Zero-trust streaming validation
        validated = process_and_validate_upload_stream(
            stream=file_stream,
            raw_filename=raw_filename,
            declared_content_type=content_type,
            max_size_bytes=self.settings.max_upload_size_bytes,
        )

        # 2. Check duplicate document in tenant
        existing = await self.document_repo.get_by_checksum(
            tenant_id=current_user.tenant_id,
            checksum_sha256=validated.checksum_sha256,
        )
        if existing is not None:
            raise DuplicateDocumentException(checksum=validated.checksum_sha256)

        # 3. Generate safe internal storage key and upload
        document_id = uuid.uuid4()
        version_number = 1
        storage_path = generate_storage_path(
            tenant_id=current_user.tenant_id,
            document_id=document_id,
            version_number=version_number,
            extension=validated.extension,
            checksum=validated.checksum_sha256,
        )

        await self.storage.upload(
            key=storage_path,
            data=validated.content,
            content_type=validated.mime_type,
            metadata={
                "tenant_id": str(current_user.tenant_id),
                "owner_id": str(current_user.id),
                "original_filename": validated.sanitized_filename,
                "checksum_sha256": validated.checksum_sha256,
            },
        )

        doc_title = title.strip() if title and title.strip() else validated.sanitized_filename

        # 4. Transactional database insertion
        doc_model = await self.document_repo.create(
            id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
            title=doc_title,
            original_filename=validated.sanitized_filename,
            file_type=validated.extension,
            file_size_bytes=validated.size_bytes,
            storage_path=storage_path,
            checksum_sha256=validated.checksum_sha256,
        )


        version_model = await self.version_repo.create(
            document_id=doc_model.id,
            version_number=version_number,
            storage_path=storage_path,
            file_size_bytes=validated.size_bytes,
            checksum_sha256=validated.checksum_sha256,
        )

        doc_model.current_version_id = version_model.id

        await self.asset_repo.create(
            document_id=doc_model.id,
            version_id=version_model.id,
            asset_type="ORIGINAL",
            storage_path=storage_path,
            mime_type=validated.mime_type,
            size_bytes=validated.size_bytes,
            asset_metadata={
                "original_filename": validated.original_filename,
                "sanitized_filename": validated.sanitized_filename,
            },
        )

        job_model = await self.job_repo.create(
            document_id=doc_model.id,
            version_id=version_model.id,
            status="UPLOADED",
            stage="INGESTION",
            progress_percent=0,
        )

        # Audit log
        await self.audit_repo.log_action(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            resource_id=doc_model.id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "filename": validated.sanitized_filename,
                "file_type": validated.extension,
                "file_size": validated.size_bytes,
                "checksum_sha256": validated.checksum_sha256,
                "job_id": str(job_model.id),
            },
        )

        await self.session.commit()
        await self.session.refresh(doc_model)
        await self.session.refresh(job_model)

        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(doc_model),
            job=ProcessingJobSummary.model_validate(job_model),
            message="Document uploaded successfully and queued for processing.",
        )

    async def list_documents(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        file_type: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> DocumentListResponse:
        """List documents with pagination, filtering, search, and tenant/role isolation."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        items, total_items = await self.document_repo.list_paginated(
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
            page=page,
            page_size=page_size,
            file_type=file_type,
            search=search,
            sort_by=sort_by,
            order=order,
        )

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1

        pagination = PaginationMetadata(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

        return DocumentListResponse(
            items=[DocumentResponse.model_validate(item) for item in items],
            pagination=pagination,
        )

    async def get_document_detail(
        self,
        document_id: uuid.UUID,
        current_user: User,
    ) -> DocumentDetailResponse:
        """Retrieve full details of a document including versions, assets, and latest job."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        doc = await self.document_repo.get_detail(
            document_id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
        )
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        latest_job = await self.job_repo.get_latest_for_document(document_id=document_id)

        return DocumentDetailResponse(
            id=doc.id,
            tenant_id=doc.tenant_id,
            owner_id=doc.owner_id,
            title=doc.title,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size_bytes=doc.file_size_bytes,
            storage_path=doc.storage_path,
            checksum_sha256=doc.checksum_sha256,
            is_deleted=doc.is_deleted,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            versions=[DocumentVersionSummary.model_validate(v) for v in (doc.versions or [])],
            assets=[DocumentAssetSummary.model_validate(a) for a in (doc.assets or [])],
            latest_job=ProcessingJobSummary.model_validate(latest_job) if latest_job else None,
        )

    async def delete_document(
        self,
        document_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> DocumentMessageResponse:
        """Soft delete a document and log the action in audit trail."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        doc = await self.document_repo.get_by_id_scoped(
            document_id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
            include_deleted=False,
        )
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        await self.document_repo.soft_delete(document_id=document_id)

        await self.audit_repo.log_action(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            action="DOCUMENT_DELETED",
            resource_type="document",
            resource_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"title": doc.title, "filename": doc.original_filename},
        )

        await self.session.commit()

        return DocumentMessageResponse(
            message="Document deleted successfully.",
            document_id=document_id,
        )
