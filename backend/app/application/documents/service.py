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
from app.infrastructure.chunking import ChunkingOptions, get_chunker
from app.infrastructure.database.models import DocumentChunkModel
from app.infrastructure.database.repositories import (
    AuditLogRepository,
    DocumentAssetRepository,
    DocumentChunkRepository,
    DocumentRepository,
    DocumentVersionRepository,
    ProcessingJobRepository,
)
from app.infrastructure.normalization import DocumentNormalizer, MetadataExtractor
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
        self.chunk_repo = DocumentChunkRepository(session)
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

            # 2. Invoke DocumentProcessor (Parsing stage)
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

            # 3. Normalization & Metadata Extraction stage
            await self.job_repo.update_status(
                job_id=job.id,
                status="PROCESSING",
                stage="NORMALIZATION",
                progress_percent=50,
            )

            normalized_md = DocumentNormalizer.normalize_markdown(processed.markdown)
            cleaned_text = DocumentNormalizer.clean_text(processed.plain_text)
            normalized_ast = DocumentNormalizer.normalize_ast(processed.json_dict)

            extracted_metadata = MetadataExtractor.extract(
                markdown=normalized_md,
                plain_text=cleaned_text,
                filename=doc.original_filename,
                file_type=doc.file_type,
                checksum=version.checksum_sha256,
                page_count=processed.page_count,
                table_count=processed.table_count,
                figure_count=len(processed.figures) or processed.figure_count,
                ast_dict=normalized_ast,
            )

            # 4. Intelligent Chunking stage
            await self.job_repo.update_status(
                job_id=job.id,
                status="PROCESSING",
                stage="CHUNKING",
                progress_percent=75,
            )

            chunking_opts = ChunkingOptions(
                max_tokens=self.settings.chunk_max_tokens,
                overlap_tokens=self.settings.chunk_overlap_tokens,
                min_tokens=self.settings.chunk_min_tokens,
                preserve_tables=self.settings.chunk_preserve_tables,
                source_filename=doc.original_filename,
            )
            chunker = get_chunker(strategy=self.settings.chunking_strategy)
            chunks = chunker.chunk(
                markdown=normalized_md,
                document_id=doc.id,
                version_id=version.id,
                options=chunking_opts,
                ast_dict=normalized_ast,
            )

            # 5. Idempotently store chunks in PostgreSQL
            await self.chunk_repo.delete_by_version(version_id=version.id)
            chunk_models = [
                DocumentChunkModel(
                    id=c.chunk_id,
                    document_id=c.document_id,
                    version_id=c.version_id,
                    chunk_index=c.chunk_index,
                    content=c.text,
                    token_count=c.token_count,
                    heading_hierarchy=c.heading_hierarchy,
                    page_numbers=c.page_numbers,
                    chunk_metadata=c.chunk_metadata,
                )
                for c in chunks
            ]
            await self.chunk_repo.bulk_create(chunk_models)

            # 6. Store structured derivative artifacts in ObjectStorage
            base_key = f"tenants/{doc.tenant_id}/documents/{doc.id}/v{version.version_number}/artifacts"

            # document.json (normalized AST)
            json_key = f"{base_key}/document.json"
            json_bytes = json.dumps(normalized_ast, indent=2).encode("utf-8")
            await self.storage.upload(json_key, json_bytes, "application/json")

            # document.md (normalized Markdown)
            md_key = f"{base_key}/document.md"
            md_bytes = normalized_md.encode("utf-8")
            await self.storage.upload(md_key, md_bytes, "text/markdown")

            # document.txt (cleaned plain text)
            txt_key = f"{base_key}/document.txt"
            txt_bytes = cleaned_text.encode("utf-8")
            await self.storage.upload(txt_key, txt_bytes, "text/plain")

            # chunks.json (structured chunks export)
            chunks_key = f"{base_key}/chunks.json"
            chunks_payload = [c.to_dict() for c in chunks]
            chunks_bytes = json.dumps(chunks_payload, indent=2).encode("utf-8")
            await self.storage.upload(chunks_key, chunks_bytes, "application/json")

            # metadata.json (enriched business and structural metadata)
            meta_dict = extracted_metadata.to_dict()
            meta_dict["chunk_count"] = len(chunks)
            meta_dict["total_tokens"] = sum(c.token_count for c in chunks)
            meta_dict["avg_chunk_tokens"] = (
                round(sum(c.token_count for c in chunks) / max(1, len(chunks)), 1)
            )
            meta_dict["chunking_strategy"] = self.settings.chunking_strategy
            meta_dict["duration_ms"] = processed.duration_ms

            meta_key = f"{base_key}/metadata.json"
            meta_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
            await self.storage.upload(meta_key, meta_bytes, "application/json")

            # 7. Idempotently update database asset records
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
                asset_metadata={"word_count": extracted_metadata.word_count},
            )
            await self.asset_repo.create(
                document_id=doc.id,
                version_id=version.id,
                asset_type="CHUNKS_JSON",
                storage_path=chunks_key,
                mime_type="application/json",
                size_bytes=len(chunks_bytes),
                asset_metadata={"chunk_count": len(chunks)},
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
                    "page_count": extracted_metadata.page_count,
                    "chunk_count": len(chunks),
                    "table_count": extracted_metadata.table_count,
                    "figure_count": extracted_metadata.figure_count,
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

    async def list_document_chunks(
        self,
        document_id: uuid.UUID,
        current_user: User,
        version_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[DocumentChunkModel], int]:
        """Fetch paginated document chunks with tenant and user isolation."""
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        doc = await self.document_repo.get_by_id_scoped(
            document_id=document_id,
            tenant_id=current_user.tenant_id,
            owner_id=owner_id,
        )
        if doc is None:
            raise DocumentNotFoundException(str(document_id))

        target_version_id = version_id
        if target_version_id is None:
            latest_version = await self.version_repo.get_latest_for_document(document_id)
            if latest_version is None:
                return [], 0
            target_version_id = latest_version.id

        chunks = await self.chunk_repo.list_by_version(
            version_id=target_version_id,
            offset=offset,
            limit=limit,
        )
        total = await self.chunk_repo.count_by_version(version_id=target_version_id)
        return chunks, total


