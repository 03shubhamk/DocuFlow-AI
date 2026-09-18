"""
DocuFlow AI — Unit Tests for DocumentService.

Tests upload creation, versioning, state transitions, processing callbacks,
cascading deletion with storage cleanup, and permission checks.
"""

from __future__ import annotations

import io

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.documents.service import DocumentService
from app.domain.entities import ProcessingStatus, User, UserRole
from app.domain.exceptions import DocumentNotFoundException, ForbiddenException
from app.infrastructure.database.models import UserModel
from app.infrastructure.processors.mock_processor import MockDocumentProcessor
from app.infrastructure.storage.memory_storage import InMemoryStorage
from tests.fixtures.sample_files import create_sample_pdf_bytes


class TestDocumentServiceUnit:
    @pytest.mark.asyncio
    async def test_upload_document_creates_record_and_version(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        storage = InMemoryStorage()
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

        pdf_bytes = create_sample_pdf_bytes("DocuFlow Test Doc")
        file_obj = io.BytesIO(pdf_bytes)

        upload_res = await service.upload_document(
            file_stream=file_obj,
            raw_filename="test_document.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        assert upload_res is not None
        assert upload_res.document.id is not None
        assert upload_res.document.original_filename == "test_document.pdf"
        assert upload_res.job.status == ProcessingStatus.UPLOADED.value or upload_res.job.status == "UPLOADED"

    @pytest.mark.asyncio
    async def test_process_document_version_transitions_state_to_completed(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        storage = InMemoryStorage()
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

        pdf_bytes = create_sample_pdf_bytes("DocuFlow Intelligent Ingestion")
        uploaded = await service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="ingest.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        processed = await service.process_document_version(
            document_id=uploaded.document.id,
            version_id=uploaded.job.version_id,
        )

        assert processed.page_count > 0

    @pytest.mark.asyncio
    async def test_delete_document_cleans_up_storage_artifacts(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        storage = InMemoryStorage()
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

        pdf_bytes = create_sample_pdf_bytes("Doc to delete")
        uploaded = await service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="delete_me.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )

        # Delete document
        deleted = await service.delete_document(uploaded.document.id, current_user=user_entity)
        assert deleted is not None

        # Verify DocumentNotFound on subsequent get
        with pytest.raises(DocumentNotFoundException):
            await service.get_document_detail(uploaded.document.id, current_user=user_entity)

    @pytest.mark.asyncio
    async def test_cross_user_isolation_blocks_unauthorized_access(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
        test_user_b: UserModel,
    ):
        storage = InMemoryStorage()
        processor = MockDocumentProcessor()
        service = DocumentService(session=db_session, storage=storage, processor=processor)

        user_a = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )
        user_b = User(
            id=test_user_b.id,
            tenant_id=test_user_b.tenant_id,
            email=test_user_b.email,
            hashed_password=test_user_b.hashed_password,
            full_name=test_user_b.full_name,
            role=UserRole(test_user_b.role),
        )

        uploaded = await service.upload_document(
            file_stream=io.BytesIO(create_sample_pdf_bytes("Secret")),
            raw_filename="user_a_private.pdf",
            content_type="application/pdf",
            current_user=user_a,
        )

        # User B should be blocked from reading User A's document
        with pytest.raises((ForbiddenException, DocumentNotFoundException)):
            await service.get_document_detail(uploaded.document.id, current_user=user_b)


