"""
DocuFlow AI — Document Upload Validation & Sanitization Engine.

Enforces zero-trust file validation:
1. Strict extension whitelisting
2. Magic byte / header sniffing to prevent MIME spoofing
3. Path traversal sanitization
4. Streaming SHA-256 calculation & size enforcement
5. Safe internal storage key generation
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.domain.exceptions import FileTooLargeException, InvalidFileException

# Canonical supported extensions mapped to expected MIME types
SUPPORTED_FORMATS: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "application/octet-stream",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
    ".html": {"text/html", "application/xhtml+xml", "text/plain"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".txt": {"text/plain", "text/csv"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".tiff": {"image/tiff"},
}

CANONICAL_MIME_BY_EXT: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
}

# Magic signatures
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".docx": [b"PK\x03\x04"],
    ".pptx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
}


@dataclass
class ValidatedUpload:
    """Represents a fully validated and hashed file upload payload."""

    content: bytes
    original_filename: str
    sanitized_filename: str
    extension: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str


def sanitize_filename(filename: str) -> str:
    """Sanitize and strip dangerous path traversal characters from filename."""
    if not filename or not filename.strip():
        raise InvalidFileException("Filename cannot be empty.")

    # Remove null bytes
    cleaned = filename.replace("\x00", "")

    # Strip directory components (both / and \)
    cleaned = os.path.basename(cleaned)
    cleaned = cleaned.replace("\\", "/").split("/")[-1]

    # Remove dangerous characters, allow alphanumerics, underscores, hyphens, periods, spaces
    cleaned = re.sub(r"[^\w\s\.-]", "", cleaned).strip()

    if not cleaned or cleaned in {".", ".."}:
        return f"document_{uuid.uuid4().hex[:8]}"

    return cleaned[:255]


def validate_extension(filename: str) -> str:
    """Validate and return normalized lowercase extension."""
    suffix = Path(filename).suffix.lower()
    if not suffix or suffix not in SUPPORTED_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_FORMATS.keys()))
        raise InvalidFileException(
            f"Unsupported file extension '{suffix or 'none'}'. Supported extensions: {allowed}"
        )
    return suffix


def validate_magic_bytes(header: bytes, extension: str) -> None:
    """Verify that file header bytes match the expected file type signatures."""
    if not header:
        raise InvalidFileException("File is empty (0 bytes).")

    # Binary signatures check
    if extension in MAGIC_SIGNATURES:
        expected_signatures = MAGIC_SIGNATURES[extension]
        if not any(header.startswith(sig) for sig in expected_signatures):
            raise InvalidFileException(
                f"File content does not match declared format '{extension}'. Magic header mismatch."
            )
        return

    # Text formats check (.txt, .md, .html)
    # Reject binary files containing null bytes pretending to be text
    if extension in {".txt", ".md", ".html"}:
        if b"\x00" in header[:1024]:
            raise InvalidFileException(
                f"Binary content detected in text file declaring extension '{extension}'."
            )


def process_and_validate_upload_stream(
    stream: BinaryIO,
    raw_filename: str,
    declared_content_type: str | None,
    max_size_bytes: int,
    chunk_size: int = 65536,
) -> ValidatedUpload:
    """Stream, validate size, compute SHA-256, verify magic bytes and return validated upload object."""
    sanitized_name = sanitize_filename(raw_filename)
    extension = validate_extension(sanitized_name)

    sha256_hasher = hashlib.sha256()
    total_size = 0
    chunks: list[bytes] = []
    header = b""

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > max_size_bytes:
            raise FileTooLargeException(
                filename=sanitized_name,
                size_bytes=total_size,
                max_bytes=max_size_bytes,
            )

        if not header:
            header = chunk[:1024]
            validate_magic_bytes(header, extension)

        sha256_hasher.update(chunk)
        chunks.append(chunk)

    if total_size == 0:
        raise InvalidFileException("Uploaded file is empty (0 bytes).")

    full_content = b"".join(chunks)
    checksum = sha256_hasher.hexdigest()

    # Determine resolved MIME type
    canonical_mime = CANONICAL_MIME_BY_EXT.get(extension, "application/octet-stream")
    if declared_content_type and declared_content_type.lower() in SUPPORTED_FORMATS.get(extension, set()):
        resolved_mime = declared_content_type.lower()
    else:
        resolved_mime = canonical_mime

    return ValidatedUpload(
        content=full_content,
        original_filename=raw_filename,
        sanitized_filename=sanitized_name,
        extension=extension,
        mime_type=resolved_mime,
        size_bytes=total_size,
        checksum_sha256=checksum,
    )


def generate_storage_path(
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    version_number: int,
    extension: str,
    checksum: str,
) -> str:
    """Generate a safe, namespaced storage path preventing collisions and traversal."""
    ext = extension if extension.startswith(".") else f".{extension}"
    return f"tenants/{tenant_id}/documents/{document_id}/v{version_number}/{document_id.hex[:12]}_{checksum[:8]}{ext}"
