"""
DocuFlow AI — Unit Tests for Validation Engine.

Tests zero-trust filename sanitization, extension validation, magic byte checking,
streaming size limits, SHA-256 calculation, and storage path generation.
"""

from __future__ import annotations

import io
import uuid

import pytest

from app.application.documents.validation import (
    generate_storage_path,
    process_and_validate_upload_stream,
    sanitize_filename,
    validate_extension,
    validate_magic_bytes,
)
from app.domain.exceptions import FileTooLargeException, InvalidFileException


def test_sanitize_filename_prevents_path_traversal() -> None:
    # Linux path traversal
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    # Windows path traversal
    assert sanitize_filename("..\\..\\windows\\system32\\calc.exe.pdf") == "calc.exe.pdf"
    # Null byte injection
    assert sanitize_filename("malicious.pdf\x00.exe") == "malicious.pdf.exe"
    # Clean standard filename
    assert sanitize_filename("Quarterly_Report_2026.pdf") == "Quarterly_Report_2026.pdf"


def test_sanitize_filename_empty_or_invalid() -> None:
    with pytest.raises(InvalidFileException):
        sanitize_filename("")

    with pytest.raises(InvalidFileException):
        sanitize_filename("   ")


def test_validate_extension_all_supported_formats() -> None:
    formats = [
        "file.pdf",
        "doc.docx",
        "slide.pptx",
        "sheet.xlsx",
        "page.html",
        "notes.md",
        "plain.txt",
        "image.png",
        "photo.jpg",
        "photo.jpeg",
        "scan.tiff",
    ]
    for filename in formats:
        ext = validate_extension(filename)
        assert ext.startswith(".")


def test_validate_extension_unsupported_format() -> None:
    with pytest.raises(InvalidFileException) as exc_info:
        validate_extension("payload.exe")
    assert "Unsupported file extension" in str(exc_info.value)

    with pytest.raises(InvalidFileException):
        validate_extension("script.sh")

    with pytest.raises(InvalidFileException):
        validate_extension("noextension")


def test_validate_magic_bytes_valid_signatures() -> None:
    # PDF
    validate_magic_bytes(b"%PDF-1.7\n...", ".pdf")
    # PNG
    validate_magic_bytes(b"\x89PNG\r\n\x1a\n\x00\x00", ".png")
    # JPEG
    validate_magic_bytes(b"\xff\xd8\xff\xe0\x00\x10", ".jpg")
    # TIFF
    validate_magic_bytes(b"II*\x00\x08\x00", ".tiff")
    # DOCX / PPTX / XLSX (Zip header)
    validate_magic_bytes(b"PK\x03\x04\x14\x00", ".docx")
    validate_magic_bytes(b"PK\x03\x04\x14\x00", ".xlsx")


def test_validate_magic_bytes_mismatch_raises() -> None:
    # EXE disguised as PDF
    with pytest.raises(InvalidFileException) as exc_info:
        validate_magic_bytes(b"MZ\x90\x00\x03\x00", ".pdf")
    assert "Magic header mismatch" in str(exc_info.value)

    # Plain text disguised as PNG
    with pytest.raises(InvalidFileException):
        validate_magic_bytes(b"Hello world this is not a png", ".png")


def test_validate_magic_bytes_binary_in_text_file() -> None:
    # Text file containing binary null bytes
    with pytest.raises(InvalidFileException) as exc_info:
        validate_magic_bytes(b"Text\x00\x01\x02BinaryData", ".txt")
    assert "Binary content detected in text file" in str(exc_info.value)


def test_process_and_validate_upload_stream_success() -> None:
    content = b"%PDF-1.4\nTest PDF content with valid header."
    stream = io.BytesIO(content)

    validated = process_and_validate_upload_stream(
        stream=stream,
        raw_filename="Quarterly.pdf",
        declared_content_type="application/pdf",
        max_size_bytes=1024 * 1024,
    )

    assert validated.original_filename == "Quarterly.pdf"
    assert validated.sanitized_filename == "Quarterly.pdf"
    assert validated.extension == ".pdf"
    assert validated.mime_type == "application/pdf"
    assert validated.size_bytes == len(content)
    assert len(validated.checksum_sha256) == 64


def test_process_and_validate_upload_stream_oversized() -> None:
    content = b"%PDF-1.4" + b"A" * 1000
    stream = io.BytesIO(content)

    with pytest.raises(FileTooLargeException) as exc_info:
        process_and_validate_upload_stream(
            stream=stream,
            raw_filename="Large.pdf",
            declared_content_type="application/pdf",
            max_size_bytes=500,  # Max 500 bytes
            chunk_size=128,
        )
    assert "exceeds the maximum allowed size" in str(exc_info.value)


def test_process_and_validate_upload_stream_empty() -> None:
    stream = io.BytesIO(b"")

    with pytest.raises(InvalidFileException) as exc_info:
        process_and_validate_upload_stream(
            stream=stream,
            raw_filename="Empty.pdf",
            declared_content_type="application/pdf",
            max_size_bytes=1024,
        )
    assert "empty" in str(exc_info.value).lower()


def test_generate_storage_path() -> None:
    t_id = uuid.uuid4()
    d_id = uuid.uuid4()
    checksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    path = generate_storage_path(
        tenant_id=t_id,
        document_id=d_id,
        version_number=1,
        extension=".pdf",
        checksum=checksum,
    )

    assert path.startswith(f"tenants/{t_id}/documents/{d_id}/v1/")
    assert path.endswith(".pdf")
    assert checksum[:8] in path
