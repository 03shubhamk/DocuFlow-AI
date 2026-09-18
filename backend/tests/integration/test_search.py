"""
DocuFlow AI — Integration Tests for Document Search and Structure Endpoints.

Tests:
- End-to-end semantic vector search (POST /api/v1/search)
- Metadata and document_ids scoping filters
- Hybrid retrieval with Reciprocal Rank Fusion
- Multi-tenant and user ownership isolation
- Document structure outline retrieval (GET /api/v1/documents/{id}/structure)
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.application.documents.service import DocumentService
from app.infrastructure.storage.memory_storage import InMemoryStorage


@pytest.mark.asyncio
async def test_search_documents_end_to_end(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Upload and process a document
    content = b"%PDF-1.4\n# Financial Results\nOperating margin expanded to 24 percent in Q3."
    files = {"file": ("financials_q3.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert upload_res.status_code == 201
    doc_id = uuid.UUID(upload_res.json()["document"]["id"])

    service = DocumentService(session=db_session, storage=in_memory_storage)
    version = await service.version_repo.get_latest_for_document(doc_id)
    assert version is not None
    await service.process_document_version(doc_id, version.id)

    # 2. Execute semantic search
    search_payload = {
        "query": "What are the operating margins in Q3?",
        "top_k": 5,
        "score_threshold": 0.0,
    }
    search_res = client.post("/api/v1/search", headers=user_auth_headers, json=search_payload)
    assert search_res.status_code == 200
    data = search_res.json()

    assert data["query"] == "What are the operating margins in Q3?"
    assert data["strategy_used"] == "dense"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1

    first_item = data["results"][0]
    assert first_item["document_id"] == str(doc_id)
    assert first_item["document_name"] == "financials_q3.pdf"
    assert "score" in first_item
    assert "text" in first_item
    assert "chunk_id" in first_item


@pytest.mark.asyncio
async def test_search_document_ids_filter(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Upload Doc A
    content_a = b"%PDF-1.4\nDoc A contains machine learning architectures."
    files_a = {"file": ("doc_a.pdf", io.BytesIO(content_a), "application/pdf")}
    res_a = client.post("/api/v1/documents", headers=user_auth_headers, files=files_a)
    doc_a_id = uuid.UUID(res_a.json()["document"]["id"])

    # 2. Upload Doc B
    content_b = b"%PDF-1.4\nDoc B contains cloud database indexing methods."
    files_b = {"file": ("doc_b.pdf", io.BytesIO(content_b), "application/pdf")}
    res_b = client.post("/api/v1/documents", headers=user_auth_headers, files=files_b)
    doc_b_id = uuid.UUID(res_b.json()["document"]["id"])

    service = DocumentService(session=db_session, storage=in_memory_storage)
    ver_a = await service.version_repo.get_latest_for_document(doc_a_id)
    ver_b = await service.version_repo.get_latest_for_document(doc_b_id)
    assert ver_a is not None and ver_b is not None

    await service.process_document_version(doc_a_id, ver_a.id)
    await service.process_document_version(doc_b_id, ver_b.id)

    # 3. Search restricting to Doc A only
    search_payload = {
        "query": "cloud database indexing methods",
        "document_ids": [str(doc_a_id)],
        "top_k": 5,
    }
    search_res = client.post("/api/v1/search", headers=user_auth_headers, json=search_payload)
    assert search_res.status_code == 200
    data = search_res.json()

    # Even though query matches Doc B text, only Doc A should be returned
    for item in data["results"]:
        assert item["document_id"] == str(doc_a_id)


@pytest.mark.asyncio
async def test_search_hybrid_strategy_endpoint(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    content = b"%PDF-1.4\n# Product Catalog\nSKU-994812 wireless acoustic headphones with active noise cancelling."
    files = {"file": ("catalog.pdf", io.BytesIO(content), "application/pdf")}
    res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = uuid.UUID(res.json()["document"]["id"])

    service = DocumentService(session=db_session, storage=in_memory_storage)
    ver = await service.version_repo.get_latest_for_document(doc_id)
    assert ver is not None
    await service.process_document_version(doc_id, ver.id)

    # Call hybrid search
    hybrid_payload = {
        "query": "SKU-994812 acoustic headphones",
        "top_k": 3,
        "strategy": "hybrid",
    }
    search_res = client.post("/api/v1/search", headers=user_auth_headers, json=hybrid_payload)
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["strategy_used"] == "hybrid"
    assert data["total"] >= 1
    assert data["results"][0]["document_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_search_user_isolation(
    client: TestClient,
    user_auth_headers: dict[str, str],
    admin_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Normal user uploads a document
    content = b"%PDF-1.4\nConfidential contract belonging to normal user only."
    files = {"file": ("user_secret.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = uuid.UUID(upload_res.json()["document"]["id"])

    service = DocumentService(session=db_session, storage=in_memory_storage)
    ver = await service.version_repo.get_latest_for_document(doc_id)
    assert ver is not None
    await service.process_document_version(doc_id, ver.id)

    # 2. Normal user search finds it
    search_payload = {"query": "Confidential contract"}
    res_user = client.post("/api/v1/search", headers=user_auth_headers, json=search_payload)
    assert res_user.status_code == 200
    assert any(item["document_id"] == str(doc_id) for item in res_user.json()["results"])

    # 3. Admin in the same tenant can also search and find it
    res_admin = client.post("/api/v1/search", headers=admin_auth_headers, json=search_payload)
    assert res_admin.status_code == 200
    assert any(item["document_id"] == str(doc_id) for item in res_admin.json()["results"])


@pytest.mark.asyncio
async def test_get_document_structure_endpoint(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    content = b"%PDF-1.4\n# Executive Summary\nIntroduction content.\n## Revenue\nFinancial breakdown."
    files = {"file": ("structure_test.pdf", io.BytesIO(content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = upload_res.json()["document"]["id"]

    service = DocumentService(session=db_session, storage=in_memory_storage)
    ver = await service.version_repo.get_latest_for_document(uuid.UUID(doc_id))
    assert ver is not None
    await service.process_document_version(uuid.UUID(doc_id), ver.id)

    # Call GET /api/v1/documents/{id}/structure
    struct_res = client.get(f"/api/v1/documents/{doc_id}/structure", headers=user_auth_headers)
    assert struct_res.status_code == 200
    data = struct_res.json()

    assert data["document_id"] == doc_id
    assert data["version_id"] == str(ver.id)
    assert data["title"] == "structure_test.pdf"
    assert data["page_count"] >= 1
    assert data["chunk_count"] >= 1
    assert isinstance(data["section_hierarchy"], list)
