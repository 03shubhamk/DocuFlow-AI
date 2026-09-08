from __future__ import annotations

import json
import math
import os
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import structlog
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
    ProcessDocumentRequest,
    ProcessingErrorSummary,
    ProcessingJobSummary,
    ProcessingStatusResponse,
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
from app.infrastructure.processors import DocumentProcessor, get_document_processor
from app.infrastructure.processors.base import ProcessedDocument, ProcessingOptions
from app.infrastructure.storage.base import ObjectStorage

logger = structlog.get_logger(__name__)


class DocumentService:
    """Service layer managing document lifecycle, multi-tenant isolation, and background dispatch."""

    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        processor: DocumentProcessor | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.processor = processor or get_document_processor()
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

    async def process_document_version(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        options: ProcessingOptions | None = None,
    ) -> ProcessedDocument:
        """Execute full Docling parsing pipeline on a document version and store derivative artifacts."""
        doc = await self.document_repo.get_by_id(document_id)
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        version = await self.version_repo.get_by_id(version_id)
        if version is None:
            raise DocumentNotFoundException(f"Version {version_id} for document {document_id}")

        job = await self.job_repo.get_latest_for_document(document_id)
        if job is None:
            job = await self.job_repo.create(
                document_id=document_id,
                version_id=version_id,
                status="PROCESSING",
                stage="PARSING",
                progress_percent=10,
            )

        started_at = datetime.now(timezone.utc)
        await self.job_repo.update_status(
            job_id=job.id,
            status="PROCESSING",
            stage="PARSING",
            progress_percent=25,
            started_at=started_at,
        )
        await self.session.commit()

        temp_path: Path | None = None
        try:
            # 1. Download source document from storage to a temporary file
            file_bytes = await self.storage.download(version.storage_path)
            ext = doc.file_type if doc.file_type.startswith(".") else f".{doc.file_type}"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                temp_path = Path(tmp.name)

            # 2. Invoke DocumentProcessor
            opts = options or ProcessingOptions(
                do_ocr=self.settings.ocr_enabled,
                ocr_provider=self.settings.ocr_provider,
                ocr_languages=self.settings.ocr_languages,
            )
            processed = await self.processor.process(
                source_path=temp_path,
                mime_type=doc.file_type,
                options=opts,
            )

            # 3. Store structured derivative artifacts in ObjectStorage
            base_key = f"tenants/{doc.tenant_id}/documents/{doc.id}/v{version.version_number}/artifacts"

            # document.json
            json_key = f"{base_key}/document.json"
            json_bytes = json.dumps(processed.json_dict, indent=2).encode("utf-8")
            await self.storage.upload(json_key, json_bytes, "application/json")

            # document.md
            md_key = f"{base_key}/document.md"
            md_bytes = processed.markdown.encode("utf-8")
            await self.storage.upload(md_key, md_bytes, "text/markdown")

            # document.txt
            txt_key = f"{base_key}/document.txt"
            txt_bytes = processed.plain_text.encode("utf-8")
            await self.storage.upload(txt_key, txt_bytes, "text/plain")

            # metadata.json
            meta_key = f"{base_key}/metadata.json"
            meta_bytes = json.dumps(processed.metadata, indent=2).encode("utf-8")
            await self.storage.upload(meta_key, meta_bytes, "application/json")

            # 4. Idempotently update database records
            # Clear old derivative assets for this version to prevent duplication
            await self.asset_repo.delete_derivative_assets(version_id=version.id)

            await self.asset_repo.create(
                document_id=doc.id,
                version_id=version.id,
                asset_type="PARSED_JSON",
                storage_path=json_key,
                mime_type="application/json",
                size_bytes=len(json_bytes),
                asset_metadata={"schema": "DoclingDocument", "version": "1.0.0"},
            )
            await self.asset_repo.create(
                document_id=doc.id,
                version_id=version.id,
                asset_type="EXPORT_MARKDOWN",
                storage_path=md_key,
                mime_type="text/markdown",
                size_bytes=len(md_bytes),
                asset_metadata={"word_count": processed.metadata.get("word_count", 0)},
            )

            # Extracted figures
            for fig_name, fig_bytes in processed.figures.items():
                fig_key = f"tenants/{doc.tenant_id}/documents/{doc.id}/v{version.version_number}/figures/{fig_name}"
                await self.storage.upload(fig_key, fig_bytes, "image/png")
                await self.asset_repo.create(
                    document_id=doc.id,
                    version_id=version.id,
                    asset_type="EXTRACTED_IMAGE",
                    storage_path=fig_key,
                    mime_type="image/png",
                    size_bytes=len(fig_bytes),
                    asset_metadata={"figure_name": fig_name},
                )

            completed_at = datetime.now(timezone.utc)
            await self.job_repo.update_status(
                job_id=job.id,
                status="COMPLETED",
                stage="INDEXING_READY",
                progress_percent=100,
                completed_at=completed_at,
            )

            await self.audit_repo.log_action(
                tenant_id=doc.tenant_id,
                user_id=doc.owner_id,
                action="DOCUMENT_PROCESSED",
                resource_type="document",
                resource_id=doc.id,
                details={
                    "version_id": str(version.id),
                    "duration_ms": processed.duration_ms,
                    "page_count": processed.page_count,
                    "table_count": processed.table_count,
                    "figure_count": processed.figure_count,
                },
            )

            await self.session.commit()
            return processed

        except Exception as e:
            stack = traceback.format_exc()
            logger.error("document_processing_error", document_id=str(document_id), error=str(e))
            await self.job_repo.create_error(
                job_id=job.id,
                document_id=document_id,
                stage="PARSING",
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=stack,
                retryable=False,
            )
            await self.job_repo.update_status(
                job_id=job.id,
                status="FAILED",
                stage="PARSING",
                progress_percent=0,
            )
            await self.audit_repo.log_action(
                tenant_id=doc.tenant_id,
                user_id=doc.owner_id,
                action="DOCUMENT_PROCESSING_FAILED",
                resource_type="document",
                resource_id=doc.id,
                details={"error": str(e)},
            )
            await self.session.commit()
            raise

        finally:
            if temp_path and temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def trigger_processing(
        self,
        document_id: uuid.UUID,
        current_user: User,
        options: ProcessDocumentRequest | None = None,
    ) -> ProcessingJobSummary:
        """Trigger asynchronous document processing via Celery or background task."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        doc = await self.document_repo.get_by_id_scoped(
            document_id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
        )
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        version = await self.version_repo.get_latest_for_document(document_id)
        if version is None:
            raise DocumentNotFoundException(f"Version for document {document_id}")

        job = await self.job_repo.get_latest_for_document(document_id)
        if job is None:
            job = await self.job_repo.create(
                document_id=doc.id,
                version_id=version.id,
                status="QUEUED",
                stage="INGESTION",
                progress_percent=0,
            )
        else:
            await self.job_repo.update_status(
                job_id=job.id,
                status="QUEUED",
                stage="INGESTION",
                progress_percent=0,
            )
            await self.session.commit()
            await self.session.refresh(job)

        # Dispatch Celery background task
        try:
            from app.infrastructure.tasks.parsing_tasks import process_document_task

            task = process_document_task.delay(str(job.id), str(doc.id), str(version.id))
            job.celery_task_id = task.id
            await self.session.commit()
            await self.session.refresh(job)
        except Exception as queue_err:
            logger.warning("celery_dispatch_skipped_or_failed", error=str(queue_err))

        return ProcessingJobSummary.model_validate(job)

    async def get_processing_status(
        self,
        document_id: uuid.UUID,
        current_user: User,
    ) -> ProcessingStatusResponse:
        """Retrieve real-time processing status, progress, error diagnostics, and artifacts."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        doc = await self.document_repo.get_by_id_scoped(
            document_id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
        )
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        version = await self.version_repo.get_latest_for_document(document_id)
        version_id = version.id if version else doc.id

        job = await self.job_repo.get_latest_for_document(document_id)
        if job is None:
            raise DocumentNotFoundException(f"Processing job for document {document_id}")

        errors = await self.job_repo.get_errors_for_job(job.id)
        assets = await self.asset_repo.list_by_version(version_id)

        duration_ms = None
        if job.started_at and job.completed_at:
            duration_ms = round((job.completed_at - job.started_at).total_seconds() * 1000, 2)

        return ProcessingStatusResponse(
            document_id=doc.id,
            version_id=version_id,
            job_id=job.id,
            status=job.status,
            stage=job.stage,
            progress_percent=job.progress_percent,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_ms=duration_ms,
            errors=[ProcessingErrorSummary.model_validate(e) for e in errors],
            artifacts_created=[a.storage_path for a in assets],
        )

