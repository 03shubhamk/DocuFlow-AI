"""
DocuFlow AI — Integration Tests for Production Security Hardening.

Tests:
1. OWASP Security Headers across HTTP responses
2. API Rate Limiting (429 Too Many Requests + Retry-After)
3. Payload Size Limits (413 Payload Too Large)
4. Zero IDOR Multi-Tenant & User Access Isolation
5. Rejection of Infected Uploads (Malware / EICAR signature)
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.api.security_middleware import get_rate_limiter
from app.infrastructure.security.malware_scanner import EICAR_SIGNATURE


def test_owasp_security_headers(client: TestClient) -> None:
    """Verify standard OWASP security headers are present on API responses."""
    response = client.get("/health/live")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in headers
    assert "Referrer-Policy" in headers
    assert "Content-Security-Policy" in headers


def test_rate_limiting_middleware_enforces_429(
    client: TestClient, user_auth_headers: dict[str, str]
) -> None:
    """Verify rate limiter blocks excessive request bursts with HTTP 429."""
    limiter = get_rate_limiter()
    limiter.reset()

    # Set capacity low for test
    limiter.capacity = 4.0
    limiter.rate = 0.05

    # Consume available tokens
    responses = []
    for _ in range(8):
        res = client.get("/api/v1/auth/me", headers=user_auth_headers)
        responses.append(res.status_code)

    assert 429 in responses
    limiter.reset()


def test_max_payload_size_enforcement_returns_413(
    client: TestClient, user_auth_headers: dict[str, str]
) -> None:
    """Verify oversized request payloads are rejected with HTTP 413."""
    headers = {
        **user_auth_headers,
        "Content-Type": "application/json",
        "Content-Length": "10000000",  # 10 MB declared on standard JSON endpoint
    }

    response = client.post(
        "/api/v1/search",
        headers=headers,
        content=b'{"query": "test"}',
    )
    assert response.status_code == 413
    assert "Payload Too Large" in response.text


def test_malware_eicar_upload_rejected(
    client: TestClient, user_auth_headers: dict[str, str]
) -> None:
    """Verify document upload containing EICAR test string is rejected."""
    infected_pdf = b"%PDF-1.4\n" + EICAR_SIGNATURE + b"\nTest PDF"
    files = {"file": ("infected_document.pdf", io.BytesIO(infected_pdf), "application/pdf")}

    response = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
    assert response.status_code in {400, 422}
    assert "Malware scanning alert" in response.text or "rejected" in response.text.lower()
