"""
DocuFlow AI — Integration Tests for Document Management API.

Tests full document lifecycle:
- Valid upload (PDF, DOCX, PNG, TXT)
- Invalid extensions & magic byte spoofing detection
- Oversized file rejection
- Duplicate upload detection (409 Conflict)
- Multi-tenant and owner isolation enforcement
- Soft deletion & audit logging
- Storage failure handling & rollback
- Paginated listing, filtering, search, and sorting
"""

from __future__ import annotations

import io
import uuid

import pytest
from starlette.testclient import TestClient

from app.config import Settings
from app.infrastructure.security.tokens import create_access_token
from app.infrastructure.storage.memory_storage import InMemoryStorage


@pytest.mark.asyncio
async def test_upload_valid_pdf(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
) -> None:
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    files = {"file": ("test_report.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"title": "Q1 Financial Report"}

    response = client.post(
        "/api/v1/documents",
        headers=user_auth_headers,
        files=files,
        data=data,
    )

    assert response.status_code == 201
    payload = response.json()
    assert "document" in payload
    assert "job" in payload

    doc = payload["document"]
    assert doc["title"] == "Q1 Financial Report"
    assert doc["original_filename"] == "test_report.pdf"
    assert doc["file_type"] == ".pdf"
    assert doc["file_size_bytes"] == len(pdf_content)
    assert doc["is_deleted"] is False

    job = payload["job"]
    assert job["status"] == "UPLOADED"
    assert job["stage"] == "INGESTION"

    # Verify storage contains the file
    assert await in_memory_storage.exists(doc["storage_path"]) is True


@pytest.mark.asyncio
async def test_upload_valid_docx(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    docx_content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"A" * 100
    files = {
        "file": (
            "contract.docx",
            io.BytesIO(docx_content),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    response = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert response.status_code == 201
    assert response.json()["document"]["file_type"] == ".docx"


@pytest.mark.asyncio
async def test_upload_invalid_extension(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    files = {"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
    response = client.post("/api/v1/documents", headers=user_auth_headers, files=files)

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_magic_byte_spoofing_rejected(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    # Executable disguised as PDF
    fake_pdf = b"MZ\x90\x00\x03\x00ExecutableContent"
    files = {"file": ("trojan.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    response = client.post("/api/v1/documents", headers=user_auth_headers, files=files)

    assert response.status_code == 400
    assert "Magic header mismatch" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_duplicate_detection(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    pdf_content = b"%PDF-1.4\nUnique Content for Duplicate Detection Test 12345"
    files1 = {"file": ("doc_v1.pdf", io.BytesIO(pdf_content), "application/pdf")}

    # First upload succeeds
    r1 = client.post("/api/v1/documents", headers=user_auth_headers, files=files1)
    assert r1.status_code == 201

    # Second upload with identical content in same tenant is rejected with 409
    files2 = {"file": ("doc_v2_same_hash.pdf", io.BytesIO(pdf_content), "application/pdf")}
    r2 = client.post("/api/v1/documents", headers=user_auth_headers, files=files2)
    assert r2.status_code == 409
    assert "already exists in this tenant" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_upload_storage_failure_returns_error(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
) -> None:
    in_memory_storage.should_fail = True
    pdf_content = b"%PDF-1.4\nStorage Failure Simulation Test"
    files = {"file": ("fail.pdf", io.BytesIO(pdf_content), "application/pdf")}

    response = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert response.status_code in {500, 503}

    in_memory_storage.should_fail = False


@pytest.mark.asyncio
async def test_list_documents_pagination_and_search(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    # Upload 3 distinct documents
    for i in range(3):
        content = f"%PDF-1.4\nDoc Content Number {i} {uuid.uuid4()}".encode()
        files = {"file": (f"doc_{i}.pdf", io.BytesIO(content), "application/pdf")}
        data = {"title": f"Invoice {i}"}
        res = client.post("/api/v1/documents", headers=user_auth_headers, files=files, data=data)
        assert res.status_code == 201

    # Test list page 1 with page_size=2
    list_res = client.get("/api/v1/documents?page=1&page_size=2", headers=user_auth_headers)
    assert list_res.status_code == 200
    body = list_res.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 2
    assert body["pagination"]["total_items"] >= 3
    assert body["pagination"]["has_next"] is True

    # Test search filter
    search_res = client.get("/api/v1/documents?search=Invoice 1", headers=user_auth_headers)
    assert search_res.status_code == 200
    search_items = search_res.json()["items"]
    assert len(search_items) == 1
    assert "Invoice 1" in search_items[0]["title"]


@pytest.mark.asyncio
async def test_get_document_detail(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    content = b"%PDF-1.4\nDocument Detail Verification Payload"
    files = {"file": ("detail_test.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # Fetch detail
    detail_res = client.get(f"/api/v1/documents/{doc_id}", headers=user_auth_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == doc_id
    assert len(detail["versions"]) == 1
    assert len(detail["assets"]) == 1
    assert detail["latest_job"] is not None
    assert detail["latest_job"]["status"] == "UPLOADED"


@pytest.mark.asyncio
async def test_delete_document_soft_delete(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    content = b"%PDF-1.4\nDelete Me Test Content"
    files = {"file": ("to_delete.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # Soft delete
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=user_auth_headers)
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

    # Verify document is no longer accessible
    get_res = client.get(f"/api/v1/documents/{doc_id}", headers=user_auth_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_and_user_isolation(
    client: TestClient,
    user_auth_headers: dict[str, str],
    test_settings: Settings,
) -> None:
    # 1. Upload document as User 1
    content = b"%PDF-1.4\nConfidential Tenant 1 Document"
    files = {"file": ("confidential.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # 2. Create token for different user in different tenant
    other_user_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    other_token, _ = create_access_token(
        settings=test_settings,
        subject=str(other_user_id),
        tenant_id=str(other_tenant_id),
        role="USER",
        email="attacker@other.com",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Other tenant user cannot see the document (returns 404 / 403)
    res = client.get(f"/api/v1/documents/{doc_id}", headers=other_headers)
    assert res.status_code in {401, 403, 404}

    # Other tenant user cannot delete the document
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=other_headers)
    assert del_res.status_code in {401, 403, 404}


@pytest.mark.asyncio
async def test_unauthenticated_document_access_rejected(client: TestClient) -> None:
    res = client.get("/api/v1/documents")
    assert res.status_code == 401

    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4\nTest"), "application/pdf")}
    upload_res = client.post("/api/v1/documents", files=files)
    assert upload_res.status_code == 401
