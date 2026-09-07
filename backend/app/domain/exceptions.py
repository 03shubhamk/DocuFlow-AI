"""
DocuFlow AI — Domain Exceptions.

All custom application exceptions inherit from DocuFlowException.
Error responses conform to RFC 7807 Problem Details format.
"""

from __future__ import annotations


class DocuFlowException(Exception):
    """Base exception for all DocuFlow AI application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "https://docuflow.ai/errors/internal-error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class DocumentNotFoundException(DocuFlowException):
    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document '{document_id}' not found.",
            status_code=404,
            error_type="https://docuflow.ai/errors/document-not-found",
        )


class JobNotFoundException(DocuFlowException):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            message=f"Processing job '{job_id}' not found.",
            status_code=404,
            error_type="https://docuflow.ai/errors/job-not-found",
        )


class UnsupportedFileFormatException(DocuFlowException):
    def __init__(self, filename: str, mime_type: str) -> None:
        super().__init__(
            message=f"File '{filename}' has unsupported MIME type '{mime_type}'.",
            status_code=415,
            error_type="https://docuflow.ai/errors/unsupported-file-format",
        )


class FileTooLargeException(DocuFlowException):
    def __init__(self, filename: str, size_bytes: int, max_bytes: int) -> None:
        super().__init__(
            message=(
                f"File '{filename}' ({size_bytes} bytes) exceeds the maximum "
                f"allowed size of {max_bytes} bytes."
            ),
            status_code=413,
            error_type="https://docuflow.ai/errors/file-too-large",
        )


class TenantAccessViolationException(DocuFlowException):
    def __init__(self) -> None:
        super().__init__(
            message="Access to this resource is not permitted for the current tenant.",
            status_code=403,
            error_type="https://docuflow.ai/errors/tenant-access-violation",
        )


class InvalidCredentialsException(DocuFlowException):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid email address or password.",
            status_code=401,
            error_type="https://docuflow.ai/errors/invalid-credentials",
        )


class TokenExpiredException(DocuFlowException):
    def __init__(self) -> None:
        super().__init__(
            message="Authentication token has expired. Please log in again.",
            status_code=401,
            error_type="https://docuflow.ai/errors/token-expired",
        )


class InvalidStateTransitionException(DocuFlowException):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Cannot transition processing job from '{current}' to '{target}'.",
            status_code=409,
            error_type="https://docuflow.ai/errors/invalid-state-transition",
        )


class DuplicateDocumentException(DocuFlowException):
    def __init__(self, checksum: str) -> None:
        super().__init__(
            message=f"A document with checksum '{checksum}' already exists in this tenant.",
            status_code=409,
            error_type="https://docuflow.ai/errors/duplicate-document",
        )


class StorageException(DocuFlowException):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=503,
            error_type="https://docuflow.ai/errors/storage-unavailable",
        )
