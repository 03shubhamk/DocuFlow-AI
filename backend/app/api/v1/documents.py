"""
DocuFlow AI — Documents API Router.

Provides authenticated endpoints for:
- Production-grade zero-trust document uploads
- Paginated, filtered, and sorted document listings
- Detailed document graph inspection (versions, assets, job status)
- Soft deletion with full audit trail logging
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)

from app.api.dependencies import CurrentUser, DbSession, StorageDep
from app.application.documents.schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMessageResponse,
    DocumentUploadResponse,
    ProcessDocumentRequest,
    ProcessingJobSummary,
    ProcessingStatusResponse,
)
from app.application.documents.service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentUploadResponse,
    summary="Upload and register a document",
    description=(
        "Securely upload a document (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG, JPEG, TIFF). "
        "Validates magic bytes, checks for duplicates, stores the file in object storage, "
        "records metadata across database models, and queues asynchronous processing."
    ),
)
async def upload_document(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    file: Annotated[UploadFile, File(description="Document file to upload")],
    title: Annotated[str | None, Form(description="Optional custom document title")] = None,
) -> DocumentUploadResponse:

    service = DocumentService(session=db, storage=storage)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.upload_document(
        file_stream=file.file,
        raw_filename=file.filename or "unknown",
        content_type=file.content_type,
        current_user=current_user.to_entity(),
        title=title,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List accessible documents",
    description="Retrieve a paginated list of documents with optional filtering, search, and sorting.",
)
async def list_documents(
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    file_type: str | None = Query(default=None, description="Filter by extension (e.g. .pdf, .docx)"),
    search: str | None = Query(default=None, description="Search keyword in title or filename"),
    sort_by: str = Query(
        default="created_at",
        pattern="^(created_at|title|file_size_bytes)$",
        description="Field to sort by",
    ),
    order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction"),
) -> DocumentListResponse:
    service = DocumentService(session=db, storage=storage)
    return await service.list_documents(
        current_user=current_user.to_entity(),
        page=page,
        page_size=page_size,
        file_type=file_type,
        search=search,
        sort_by=sort_by,
        order=order,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details",
    description="Retrieve full metadata, version snapshots, derived assets, and latest job status for a document.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
) -> DocumentDetailResponse:
    service = DocumentService(session=db, storage=storage)
    return await service.get_document_detail(
        document_id=document_id,
        current_user=current_user.to_entity(),
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentMessageResponse,
    summary="Delete a document",
    description="Soft-delete a document and log the action in the immutable audit trail.",
)
async def delete_document(
    request: Request,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
) -> DocumentMessageResponse:
    service = DocumentService(session=db, storage=storage)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await service.delete_document(
        document_id=document_id,
        current_user=current_user.to_entity(),
        ip_address=client_ip,
        user_agent=user_agent,
    )


@router.post(
    "/{document_id}/process",
    response_model=ProcessingJobSummary,
    summary="Trigger asynchronous document intelligence processing",
    description="Queue the document version for Docling parsing, OCR, and structural extraction.",
)
async def process_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    body: ProcessDocumentRequest | None = None,
) -> ProcessingJobSummary:
    service = DocumentService(session=db, storage=storage)
    return await service.trigger_processing(
        document_id=document_id,
        current_user=current_user.to_entity(),
        options=body,
    )


@router.get(
    "/{document_id}/processing-status",
    response_model=ProcessingStatusResponse,
    summary="Get document processing status and diagnostics",
    description="Retrieve real-time processing stage, progress percentage, error logs, and generated artifacts.",
)
async def get_processing_status(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
) -> ProcessingStatusResponse:
    service = DocumentService(session=db, storage=storage)
    return await service.get_processing_status(
        document_id=document_id,
        current_user=current_user.to_entity(),
    )


