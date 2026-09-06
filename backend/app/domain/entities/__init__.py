"""
DocuFlow AI — Domain Entities.

Pure Python dataclasses with no external framework dependencies.
These represent the core business concepts of the domain.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProcessingStatus(str, Enum):
    """Valid states in the document ingestion state machine."""

    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class UserRole(str, Enum):
    """RBAC roles for platform users."""

    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class AssetType(str, Enum):
    """Types of derivative assets produced during document ingestion."""

    ORIGINAL = "ORIGINAL"
    PARSED_JSON = "PARSED_JSON"
    EXPORT_MARKDOWN = "EXPORT_MARKDOWN"
    EXTRACTED_IMAGE = "EXTRACTED_IMAGE"
    TABLE_CSV = "TABLE_CSV"


@dataclass
class Tenant:
    """Represents an isolated organizational workspace."""

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class User:
    """Represents a platform operator or consumer within a tenant."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Document:
    """Represents the root entity of an ingested document."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    storage_path: str
    checksum_sha256: str
    is_deleted: bool = False
    current_version_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentVersion:
    """Immutable snapshot of a document at a specific version number."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    storage_path: str
    file_size_bytes: int
    checksum_sha256: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentAsset:
    """Secondary asset derived from document processing (JSON, Markdown, images)."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    asset_type: AssetType
    storage_path: str
    mime_type: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProcessingJob:
    """Tracks the asynchronous document ingestion pipeline execution."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    status: ProcessingStatus = ProcessingStatus.UPLOADED
    stage: str = "INGESTION"
    progress_percent: int = 0
    retry_count: int = 0
    max_retries: int = 3
    celery_task_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def can_retry(self) -> bool:
        """Return True if the job can be retried."""
        return self.retry_count < self.max_retries

    def can_cancel(self) -> bool:
        """Return True if the job is in a cancellable state."""
        return self.status in {ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING}


@dataclass
class DocumentChunk:
    """A semantic chunk of a document, preserving hierarchy context."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    heading_hierarchy: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    chunk_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmbeddingRecord:
    """Links a relational chunk to its vector representation in Qdrant."""

    id: uuid.UUID
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    model_name: str
    vector_dimension: int
    qdrant_point_id: uuid.UUID
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProcessingError:
    """Detailed error record for a failed processing stage."""

    id: uuid.UUID
    job_id: uuid.UUID
    document_id: uuid.UUID
    stage: str
    error_type: str
    error_message: str
    stack_trace: str | None
    retryable: bool
    created_at: datetime = field(default_factory=datetime.utcnow)
