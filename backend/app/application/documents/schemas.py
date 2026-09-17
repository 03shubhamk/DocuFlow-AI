"""
DocuFlow AI — Document Application DTO Schemas.

Pydantic schemas for document upload, listing, details, pagination, and processing jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProcessingJobSummary(BaseModel):
    """Summary of processing job status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    stage: str
    progress_percent: int
    created_at: datetime
    updated_at: datetime


class DocumentAssetSummary(BaseModel):
    """Summary of an asset associated with a document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_id: uuid.UUID
    asset_type: str
    storage_path: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class DocumentVersionSummary(BaseModel):
    """Summary of a document version snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    storage_path: str
    file_size_bytes: int
    checksum_sha256: str
    created_at: datetime


class DocumentResponse(BaseModel):
    """Response model representing a document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    storage_path: str
    checksum_sha256: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """Response returned immediately after document upload."""

    document: DocumentResponse
    job: ProcessingJobSummary
    message: str = "Document uploaded successfully and queued for processing."


class DocumentDetailResponse(DocumentResponse):
    """Detailed document response including versions, assets, and latest job."""

    versions: list[DocumentVersionSummary] = Field(default_factory=list)
    assets: list[DocumentAssetSummary] = Field(default_factory=list)
    latest_job: ProcessingJobSummary | None = None


class PaginationMetadata(BaseModel):
    """Pagination metadata model."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class DocumentListResponse(BaseModel):
    """Paginated list response for documents."""

    items: list[DocumentResponse]
    pagination: PaginationMetadata


class DocumentMessageResponse(BaseModel):
    """Generic message response."""

    message: str
    document_id: uuid.UUID


class ProcessingErrorSummary(BaseModel):
    """Summary of a processing failure error record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: str
    error_type: str
    error_message: str
    retryable: bool
    created_at: datetime


class ProcessDocumentRequest(BaseModel):
    """Optional configuration overrides for document processing."""

    do_ocr: bool | None = None
    ocr_provider: str | None = None
    extract_figures: bool = True
    do_table_structure: bool = True


class ProcessingStatusResponse(BaseModel):
    """Detailed status tracking response for document processing."""

    document_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    stage: str
    progress_percent: int
    retry_count: int
    max_retries: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    errors: list[ProcessingErrorSummary] = Field(default_factory=list)
    artifacts_created: list[str] = Field(default_factory=list)


class DocumentChunkResponse(BaseModel):
    """Structured representation of a document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    heading_hierarchy: list[str] = Field(default_factory=list)
    page_numbers: list[int] = Field(default_factory=list)
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentChunkListResponse(BaseModel):
    """Paginated list of document chunks."""

    items: list[DocumentChunkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReindexResponse(BaseModel):
    """Response returned when a document re-indexing is triggered or completed."""

    document_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    chunks_indexed: int
    model_name: str
    dimension: int
    message: str



