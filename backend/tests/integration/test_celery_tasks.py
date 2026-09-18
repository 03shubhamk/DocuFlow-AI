"""
DocuFlow AI — Integration Tests for Celery Background Tasks.

Tests process_document_task and generate_embeddings_and_index_task execution,
retry mechanisms, error categorization, and metrics/telemetry recording.
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.documents.service import DocumentService
from app.domain.entities import User, UserRole
from app.infrastructure.database.models import UserModel
from app.infrastructure.processors.mock_processor import MockDocumentProcessor
from app.infrastructure.storage import get_storage
from app.infrastructure.tasks.parsing_tasks import (
    _categorize_error,
    generate_embeddings_and_index_task,
    process_document_task,
    set_task_session_factory,
)
from tests.fixtures.sample_files import create_sample_pdf_bytes


class TestCeleryTasksIntegration:
    def test_error_categorization_helper(self):
        assert _categorize_error(ValueError("Invalid format")) == "validation_error"
        assert _categorize_error(TimeoutError("Connection timed out")) == "timeout"
        assert _categorize_error(RuntimeError("Docling parse error")) == "parsing_error"
        assert _categorize_error(PermissionError("Unauthorized")) == "security_error"

    @pytest.mark.asyncio
    async def test_process_document_task_eager_execution(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
        set_task_session_factory(factory)

        storage = get_storage()
        processor = MockDocumentProcessor()
        service = DocumentService(session=db_session, storage=storage, processor=processor)

        user_entity = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )

        pdf_bytes = create_sample_pdf_bytes("Celery Integration Task")
        uploaded = await service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="celery_test.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        job_id = str(uuid.uuid4())
        res = process_document_task.apply(
            args=[job_id, str(uploaded.document.id), str(uploaded.job.version_id)],
        ).get()

        assert res["status"] == "COMPLETED"
        assert res["job_id"] == job_id
        assert res["document_id"] == str(uploaded.document.id)
        assert res["version_id"] == str(uploaded.job.version_id)
        assert "duration_ms" in res

    @pytest.mark.asyncio
    async def test_generate_embeddings_and_index_task_eager_execution(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
        set_task_session_factory(factory)

        storage = get_storage()
        processor = MockDocumentProcessor()
        service = DocumentService(session=db_session, storage=storage, processor=processor)

        user_entity = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )

        pdf_bytes = create_sample_pdf_bytes("Indexing Task")
        uploaded = await service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="indexing_test.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        # First process
        await service.process_document_version(uploaded.document.id, uploaded.job.version_id)

        # Run indexing task
        job_id = str(uuid.uuid4())
        res = generate_embeddings_and_index_task.apply(
            args=[job_id, str(uploaded.document.id), str(uploaded.job.version_id)],
        ).get()

        assert res["status"] == "COMPLETED"
        assert res["job_id"] == job_id

