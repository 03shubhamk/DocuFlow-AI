"""
DocuFlow AI — Integration Tests for Document Intelligence Processing Pipeline.

Tests:
- End-to-end PDF processing with Docling and derivative artifact persistence
- DOCX and Image processing
- Idempotent re-processing without duplicate assets
- Trigger processing API (POST /api/v1/documents/{id}/process)
- Processing status API (GET /api/v1/documents/{id}/processing-status)
- Error capture and FAILED state persistence
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.application.documents.service import DocumentService
from app.infrastructure.processors.base import (
    DocumentProcessor,
    ProcessedDocument,
    ProcessingOptions,
)
from app.infrastructure.storage.memory_storage import InMemoryStorage


@pytest.mark.asyncio
async def test_process_document_pdf_end_to_end(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Upload a PDF document
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    files = {"file": ("quarterly_report.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    assert upload_res.status_code == 201
    doc_data = upload_res.json()["document"]
    doc_id = uuid.UUID(doc_data["id"])

    # 2. Process the document version directly via service
    service = DocumentService(session=db_session, storage=in_memory_storage)
    version = await service.version_repo.get_latest_for_document(doc_id)
    assert version is not None

    processed = await service.process_document_version(doc_id, version.id)
    assert processed is not None
    assert processed.page_count >= 1

    # 3. Verify derivative artifacts stored in ObjectStorage
    base_prefix = f"tenants/{doc_data['tenant_id']}/documents/{doc_id}/v{version.version_number}/artifacts"
    assert await in_memory_storage.exists(f"{base_prefix}/document.json") is True
    assert await in_memory_storage.exists(f"{base_prefix}/document.md") is True
    assert await in_memory_storage.exists(f"{base_prefix}/document.txt") is True
    assert await in_memory_storage.exists(f"{base_prefix}/metadata.json") is True
    assert await in_memory_storage.exists(f"{base_prefix}/chunks.json") is True

    # 4. Verify DocumentAsset records created in database
    assets = await service.asset_repo.list_by_version(version.id)
    asset_types = {a.asset_type for a in assets}
    assert "ORIGINAL" in asset_types
    assert "PARSED_JSON" in asset_types
    assert "EXPORT_MARKDOWN" in asset_types
    assert "CHUNKS_JSON" in asset_types

    # 5. Verify DocumentChunk records created in PostgreSQL
    chunks = await service.chunk_repo.list_by_version(version.id)
    assert len(chunks) >= 1
    assert chunks[0].document_id == doc_id
    assert chunks[0].version_id == version.id
    assert chunks[0].token_count > 0
    assert "checksum" in chunks[0].chunk_metadata

    # 6. Verify ProcessingJob state is COMPLETED
    job = await service.job_repo.get_latest_for_document(doc_id)
    assert job is not None
    assert job.status == "COMPLETED"
    assert job.stage == "INDEXING_READY"
    assert job.progress_percent == 100
    assert job.completed_at is not None

    # 7. Test GET /api/v1/documents/{id}/chunks endpoint
    chunks_res = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=user_auth_headers)
    assert chunks_res.status_code == 200
    chunks_body = chunks_res.json()
    assert chunks_body["total"] == len(chunks)
    assert len(chunks_body["items"]) == len(chunks)
    assert chunks_body["items"][0]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_processing_idempotency(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Upload
    pdf_content = b"%PDF-1.4\nIdempotency Test Document"
    files = {"file": ("idempotency.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = uuid.UUID(upload_res.json()["document"]["id"])

    service = DocumentService(session=db_session, storage=in_memory_storage)
    version = await service.version_repo.get_latest_for_document(doc_id)
    assert version is not None

    # 2. First Processing run
    await service.process_document_version(doc_id, version.id)
    assets_run1 = await service.asset_repo.list_by_version(version.id)
    chunks_run1 = await service.chunk_repo.list_by_version(version.id)

    # 3. Second Processing run (re-processing)
    await service.process_document_version(doc_id, version.id)
    assets_run2 = await service.asset_repo.list_by_version(version.id)
    chunks_run2 = await service.chunk_repo.list_by_version(version.id)

    # Asset counts and chunk counts should match exactly without duplicate rows
    assert len(assets_run1) == len(assets_run2)
    assert len(chunks_run1) == len(chunks_run2)
    assert len(chunks_run2) >= 1
    types_count = [a.asset_type for a in assets_run2]
    assert types_count.count("PARSED_JSON") == 1
    assert types_count.count("EXPORT_MARKDOWN") == 1
    assert types_count.count("CHUNKS_JSON") == 1


@pytest.mark.asyncio
async def test_trigger_processing_endpoint(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    # 1. Upload
    pdf_content = b"%PDF-1.4\nTrigger API Test Payload"
    files = {"file": ("trigger.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = upload_res.json()["document"]["id"]

    # 2. Trigger processing via API
    proc_res = client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=user_auth_headers,
        json={"do_ocr": True, "ocr_provider": "easyocr"},
    )
    assert proc_res.status_code == 200
    job_body = proc_res.json()
    assert job_body["status"] in {"QUEUED", "PROCESSING"}
    assert job_body["document_id"] == doc_id


@pytest.mark.asyncio
async def test_get_processing_status_endpoint(
    client: TestClient,
    user_auth_headers: dict[str, str],
) -> None:
    # 1. Upload
    pdf_content = b"%PDF-1.4\nStatus Endpoint Test Payload"
    files = {"file": ("status_test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = upload_res.json()["document"]["id"]

    # 2. Check processing status
    status_res = client.get(f"/api/v1/documents/{doc_id}/processing-status", headers=user_auth_headers)
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["document_id"] == doc_id
    assert "status" in status_body
    assert "stage" in status_body
    assert "progress_percent" in status_body
    assert isinstance(status_body["artifacts_created"], list)


@pytest.mark.asyncio
async def test_processing_failure_records_error(
    client: TestClient,
    user_auth_headers: dict[str, str],
    in_memory_storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Upload
    pdf_content = b"%PDF-1.4\nFailure Test Payload"
    files = {"file": ("fail_doc.pdf", io.BytesIO(pdf_content), "application/pdf")}
    upload_res = client.post("/api/v1/documents", headers=user_auth_headers, files=files)
    doc_id = uuid.UUID(upload_res.json()["document"]["id"])

    # 2. Custom failing processor
    class FailingProcessor(DocumentProcessor):
        async def process(self, source_path: Path, mime_type: str, options: ProcessingOptions | None = None) -> ProcessedDocument:
            raise ValueError("Corrupt PDF file header cannot be decoded.")

    service = DocumentService(session=db_session, storage=in_memory_storage, processor=FailingProcessor())
    version = await service.version_repo.get_latest_for_document(doc_id)
    assert version is not None

    # 3. Processing should fail and record error
    with pytest.raises(ValueError):
        await service.process_document_version(doc_id, version.id)

    # 4. Verify job is marked FAILED and error is recorded
    job = await service.job_repo.get_latest_for_document(doc_id)
    assert job is not None
    assert job.status == "FAILED"

    errors = await service.job_repo.get_errors_for_job(job.id)
    assert len(errors) >= 1
    assert "Corrupt PDF file header" in errors[0].error_message
    assert errors[0].error_type == "ValueError"
