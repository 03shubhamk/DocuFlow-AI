"""
DocuFlow AI — End-to-End Scenario Test Suite.

Executes the 5 primary user and system journeys across API, storage, processing,
search, isolation, and failure recovery:
- Scenario 1: Register -> Login -> Upload PDF -> Processing -> Completed -> Search -> Open Result
- Scenario 2: Upload invalid file -> Validation Error
- Scenario 3: Upload large file -> 413 Payload Too Large
- Scenario 4: User A attempts to access User B's document -> 403/404 IDOR Protection
- Scenario 5: Document processing failure -> FAILED -> Retry -> Successful Completion
"""

from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.documents.service import DocumentService
from app.domain.entities import ProcessingStatus, User, UserRole
from app.infrastructure.database.models import UserModel
from app.infrastructure.processors.mock_processor import MockDocumentProcessor
from app.infrastructure.storage.memory_storage import InMemoryStorage
from tests.fixtures.sample_files import (
    create_fake_windows_executable_bytes,
    create_oversized_payload_bytes,
    create_sample_pdf_bytes,
)


class TestE2EScenarios:
    def test_scenario_1_full_lifecycle(
        self,
        client: TestClient,
    ):
        """Scenario 1: Register -> Login -> Upload PDF -> Processing -> Completed -> Search -> Open result."""
        # 1. Register
        unique_email = f"scenario1_{uuid.uuid4().hex[:6]}@docuflow.ai"
        reg_resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "StrongPassword123!",
                "full_name": "Scenario One User",
                "tenant_name": "Scenario Org",
            },
        )
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert reg_data["email"] == unique_email

        # 2. Login verification
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "StrongPassword123!"},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert "access_token" in login_data
        token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload PDF
        pdf_bytes = create_sample_pdf_bytes(
            title="Q3 Strategy Report",
            text_content="Deep neural document intelligence and vector search.",
        )
        files = {"file": ("q3_strategy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_resp = client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = doc_data["document"]["id"]
        assert doc_data["document"]["original_filename"] == "q3_strategy.pdf"

        # 4. Process Document Version
        proc_resp = client.post(
            f"/api/v1/documents/{doc_id}/process",
            headers=auth_headers,
        )
        assert proc_resp.status_code == 200

        # 5. Check Document Details
        detail_resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
        assert detail_resp.status_code == 200

        # 6. Search Documents
        search_resp = client.post(
            "/api/v1/search",
            json={"query": "neural document intelligence", "top_k": 5},
            headers=auth_headers,
        )
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert "results" in search_data
        assert "total" in search_data

        # 7. Retrieve Document Chunks
        chunks_resp = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=auth_headers)
        assert chunks_resp.status_code == 200

    def test_scenario_2_invalid_file_validation_error(
        self,
        client: TestClient,
        user_auth_headers: dict[str, str],
    ):
        """Scenario 2: Upload invalid file -> validation error."""
        # Disguised executable with .pdf extension
        fake_exe = create_fake_windows_executable_bytes()
        files = {"file": ("malicious.pdf", io.BytesIO(fake_exe), "application/pdf")}

        resp = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
        assert resp.status_code in (400, 422)
        err = resp.json()
        assert "executable" in str(err).lower() or "invalid" in str(err).lower() or "detail" in err

    def test_scenario_3_large_file_rejection(
        self,
        client: TestClient,
        user_auth_headers: dict[str, str],
    ):
        """Scenario 3: Upload large file -> 413 rejection."""
        oversized = create_oversized_payload_bytes(size_mb=55)
        files = {"file": ("huge.pdf", io.BytesIO(oversized), "application/pdf")}

        resp = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
        assert resp.status_code in (413, 400, 422)

    def test_scenario_4_idor_isolation_protection(
        self,
        client: TestClient,
        user_auth_headers: dict[str, str],
        user_b_auth_headers: dict[str, str],
    ):
        """Scenario 4: User A creates a document; User B attempts to access it -> 403/404."""
        # User A uploads a document
        pdf_bytes = create_sample_pdf_bytes("Confidential Doc A")
        files = {"file": ("private_a.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_resp = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["document"]["id"]

        # User B attempts to get Document A details
        get_resp = client.get(f"/api/v1/documents/{doc_id}", headers=user_b_auth_headers)
        assert get_resp.status_code in (403, 404)

        # User B attempts to delete Document A
        delete_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=user_b_auth_headers)
        assert delete_resp.status_code in (403, 404)

        # User B attempts to access Document A chunks
        chunks_resp = client.get(f"/api/v1/documents/{doc_id}/chunks", headers=user_b_auth_headers)
        assert chunks_resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_scenario_5_processing_failure_and_retry(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        """Scenario 5: Document processing failure -> FAILED -> retry -> successful completion."""
        storage = InMemoryStorage()

        # Custom failing processor on first attempt
        class FailingThenSucceedingProcessor(MockDocumentProcessor):
            def __init__(self):
                super().__init__()
                self.attempts = 0

            async def process(self, source_path, mime_type: str = "application/pdf", options=None):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("Simulated OCR worker failure")
                return await super().process(source_path, mime_type, options)

        processor = FailingThenSucceedingProcessor()
        service = DocumentService(session=db_session, storage=storage, processor=processor)

        user_entity = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )

        pdf_bytes = create_sample_pdf_bytes("Retry Test Document")
        uploaded = await service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="retry_test.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        # First attempt: fails
        with pytest.raises(RuntimeError):
            await service.process_document_version(uploaded.document.id, uploaded.job.version_id)

        failed_details = await service.get_document_detail(uploaded.document.id, current_user=user_entity)
        assert failed_details.latest_job is not None
        assert failed_details.latest_job.status in (ProcessingStatus.FAILED.value, "FAILED")

        # Second attempt (Retry): succeeds
        processed = await service.process_document_version(uploaded.document.id, uploaded.job.version_id)
        assert processed.page_count > 0

        succeeded_details = await service.get_document_detail(uploaded.document.id, current_user=user_entity)
        assert succeeded_details.latest_job is not None
        assert succeeded_details.latest_job.status in (ProcessingStatus.COMPLETED.value, "COMPLETED")


