"""
DocuFlow AI — Documents Application Package.
"""

from app.application.documents.schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMessageResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.application.documents.service import DocumentService
from app.application.documents.validation import (
    SUPPORTED_FORMATS,
    ValidatedUpload,
    process_and_validate_upload_stream,
    sanitize_filename,
    validate_extension,
    validate_magic_bytes,
)

__all__ = [
    "DocumentService",
    "DocumentResponse",
    "DocumentUploadResponse",
    "DocumentDetailResponse",
    "DocumentListResponse",
    "DocumentMessageResponse",
    "ValidatedUpload",
    "SUPPORTED_FORMATS",
    "sanitize_filename",
    "validate_extension",
    "validate_magic_bytes",
    "process_and_validate_upload_stream",
]
