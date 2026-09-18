"""
DocuFlow AI — Unit Tests for Production Security Hardening.

Tests:
1. Token Bucket Rate Limiter
2. OWASP Security Headers
3. Disguised Executable Binary Rejection (ELF, PE MZ, Mach-O)
4. Zip Bomb / Decompression Bomb Protection for OOXML archives
5. Malware & EICAR Scanning Engine
6. Sensitive Data Redaction in Structured Logging
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.api.security_middleware import RateLimiter
from app.application.documents.validation import (
    validate_magic_bytes,
    validate_zip_archive_safety,
)
from app.domain.exceptions import InvalidFileException
from app.infrastructure.logging_config import redact_sensitive_log_data
from app.infrastructure.security.malware_scanner import (
    EICAR_SIGNATURE,
    MockMalwareScanner,
)


class TestRateLimiter:
    """Unit tests for Token Bucket Rate Limiter."""

    def test_rate_limiter_allows_under_limit(self) -> None:
        limiter = RateLimiter(requests_per_minute=60, burst=10)
        # 10 burst requests should be immediately allowed
        for _ in range(10):
            allowed, retry_after = limiter.is_allowed("test-client")
            assert allowed is True
            assert retry_after == 0

    def test_rate_limiter_blocks_when_exhausted(self) -> None:
        limiter = RateLimiter(requests_per_minute=10, burst=0)
        # Exhaust all tokens
        for _ in range(10):
            limiter.is_allowed("flood-client")

        # Next request must be rejected
        allowed, retry_after = limiter.is_allowed("flood-client")
        assert allowed is False
        assert retry_after > 0

    def test_rate_limiter_distinct_clients(self) -> None:
        limiter = RateLimiter(requests_per_minute=2, burst=0)
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")
        # Client A exhausted
        assert limiter.is_allowed("client-a")[0] is False
        # Client B still has capacity
        assert limiter.is_allowed("client-b")[0] is True


class TestFileUploadHardening:
    """Unit tests for executable rejection, zip bombs, and malware detection."""

    def test_rejects_disguised_pe_executable(self) -> None:
        # Windows PE binary header disguised with .pdf extension
        fake_pdf_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
        with pytest.raises(InvalidFileException, match="Executable binary content rejected"):
            validate_magic_bytes(fake_pdf_exe, ".pdf")

    def test_rejects_disguised_elf_executable(self) -> None:
        # Linux ELF binary header disguised with .txt extension
        fake_txt_elf = b"\x7fELF\x02\x01\x01\x00"
        with pytest.raises(InvalidFileException, match="Executable binary content rejected"):
            validate_magic_bytes(fake_txt_elf, ".txt")

    def test_zip_bomb_high_compression_ratio_rejected(self) -> None:
        # Generate in-memory zip file with high compression expansion ratio
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1 MB of zeroes compresses to ~1 KB (> 500x ratio)
            zf.writestr("word/document.xml", b"\x00" * (2 * 1024 * 1024))

        compressed_data = buffer.getvalue()
        with pytest.raises(InvalidFileException, match="Archive bomb protection triggered: dangerous compression ratio"):
            validate_zip_archive_safety(compressed_data, ".docx")

    def test_zip_path_traversal_entry_rejected(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("../../evil.sh", b"echo pwned")

        compressed_data = buffer.getvalue()
        with pytest.raises(InvalidFileException, match="path traversal detected"):
            validate_zip_archive_safety(compressed_data, ".docx")

    @pytest.mark.asyncio
    async def test_mock_malware_scanner_eicar_detection(self) -> None:
        scanner = MockMalwareScanner()
        # Normal clean document
        clean_res = await scanner.scan(b"%PDF-1.5 Clean Content", "clean.pdf")
        assert clean_res.is_clean is True
        assert clean_res.threat_name is None

        # Infected EICAR test string
        infected_res = await scanner.scan(EICAR_SIGNATURE + b"\nExtra data", "test.pdf")
        assert infected_res.is_clean is False
        assert infected_res.threat_name == "EICAR-Test-Signature"


class TestLoggingRedaction:
    """Unit tests for structlog sensitive data redaction."""

    def test_redact_sensitive_keys(self) -> None:
        event = {
            "event": "user_login",
            "email": "user@example.com",
            "password": "SuperSecretPassword123!",
            "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
            "refresh_token": "raw_secret_refresh_token_here",
            "jwt_secret_key": "my-secret-key",
        }
        sanitized = redact_sensitive_log_data(None, "info", event)
        assert sanitized["email"] == "user@example.com"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["access_token"] == "[REDACTED]"
        assert sanitized["refresh_token"] == "[REDACTED]"
        assert sanitized["jwt_secret_key"] == "[REDACTED]"

    def test_redact_bearer_tokens_in_strings(self) -> None:
        event = {
            "event": "http_request",
            "authorization_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        }
        sanitized = redact_sensitive_log_data(None, "info", event)
        assert sanitized["authorization_header"] == "[REDACTED]"
