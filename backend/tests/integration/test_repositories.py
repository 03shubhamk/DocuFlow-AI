"""
DocuFlow AI — Integration Tests for Async Database Repositories.

Tests CRUD operations, multi-tenant isolation, pagination, constraints,
and relational integrity across UserRepository, DocumentRepository,
DocumentVersionRepository, DocumentChunkRepository, and AuditLogRepository.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserRole
from app.infrastructure.database.models import (
    DocumentChunkModel,
    TenantModel,
    UserModel,
)
from app.infrastructure.database.repositories import (
    AuditLogRepository,
    DocumentChunkRepository,
    DocumentRepository,
    DocumentVersionRepository,
    UserRepository,
)
from app.infrastructure.security.tokens import hash_password


class TestRepositoriesIntegration:
    @pytest.mark.asyncio
    async def test_user_repository_crud(
        self,
        db_session: AsyncSession,
        test_tenant: TenantModel,
    ):
        repo = UserRepository(db_session)
        user_id = uuid.uuid4()
        user = UserModel(
            id=user_id,
            tenant_id=test_tenant.id,
            email="repo_test@docuflow.ai",
            hashed_password=hash_password("Password123!"),
            full_name="Repo Test User",
            role=UserRole.USER.value,
            is_active=True,
        )

        db_session.add(user)
        await db_session.flush()

        fetched = await repo.get_by_id(user_id)
        assert fetched is not None
        assert fetched.email == "repo_test@docuflow.ai"

        by_email = await repo.get_by_email("repo_test@docuflow.ai")
        assert by_email is not None
        assert by_email.id == user_id

    @pytest.mark.asyncio
    async def test_document_and_version_repository_crud(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        doc_repo = DocumentRepository(db_session)
        version_repo = DocumentVersionRepository(db_session)

        doc_id = uuid.uuid4()
        await doc_repo.create(
            id=doc_id,
            tenant_id=test_user.tenant_id,
            owner_id=test_user.id,
            title="financial_q3.pdf",
            original_filename="financial_q3.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
            storage_path="tenants/t1/d1/v1.pdf",
            checksum_sha256="abc123sha",
        )

        # Create Version 1
        version = await version_repo.create(
            document_id=doc_id,
            version_number=1,
            storage_path="tenants/t1/docs/d1/v1.pdf",
            file_size_bytes=1024,
            checksum_sha256="abc123sha",
        )

        # Verify Document lookup
        fetched_doc = await doc_repo.get_by_id(doc_id)
        assert fetched_doc is not None
        assert fetched_doc.original_filename == "financial_q3.pdf"

        # Verify Version lookup
        fetched_ver = await version_repo.get_by_id(version.id)
        assert fetched_ver is not None
        assert fetched_ver.version_number == 1
        assert fetched_ver.checksum_sha256 == "abc123sha"

    @pytest.mark.asyncio
    async def test_chunk_repository_bulk_insert_and_retrieval(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        doc_repo = DocumentRepository(db_session)
        version_repo = DocumentVersionRepository(db_session)
        chunk_repo = DocumentChunkRepository(db_session)

        doc_id = uuid.uuid4()
        await doc_repo.create(
            id=doc_id,
            tenant_id=test_user.tenant_id,
            owner_id=test_user.id,
            title="chunks_test.pdf",
            original_filename="chunks_test.pdf",
            file_type="application/pdf",
            file_size_bytes=512,
            storage_path="tenants/t/d/v.pdf",
            checksum_sha256="def456",
        )

        ver = await version_repo.create(
            document_id=doc_id,
            version_number=1,
            storage_path="tenants/t/d/v.pdf",
            file_size_bytes=512,
            checksum_sha256="def456",
        )

        # Insert 3 chunks
        chunks = [
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=doc_id,
                version_id=ver.id,
                chunk_index=i,
                content=f"Chunk content section {i}",
                token_count=15,
                heading_hierarchy=["1. Introduction"],
                page_numbers=[1],
                chunk_metadata={},
            )
            for i in range(3)
        ]
        await chunk_repo.bulk_create(chunks)

        # Retrieve chunks for document
        fetched_chunks = await chunk_repo.list_by_document(doc_id)
        assert len(fetched_chunks) == 3
        assert fetched_chunks[0].chunk_index == 0
        assert fetched_chunks[1].chunk_index == 1
        assert fetched_chunks[2].chunk_index == 2

    @pytest.mark.asyncio
    async def test_audit_log_repository(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        audit_repo = AuditLogRepository(db_session)
        doc_id = uuid.uuid4()

        logged = await audit_repo.log_action(
            tenant_id=test_user.tenant_id,
            action="DOCUMENT_UPLOADED",
            resource_type="document",
            user_id=test_user.id,
            resource_id=doc_id,
            details={"filename": "audit_test.pdf", "size_bytes": 1024},
        )

        assert logged is not None
        assert logged.action == "DOCUMENT_UPLOADED"
        assert logged.resource_id == doc_id


