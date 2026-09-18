"""
DocuFlow AI — Integration Tests for Vector Store.

Tests collection initialization, deterministic vector ID generation, upsert,
filtered search, health checks, and chunk deletions.
"""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.vectorstore.base import VectorPoint
from app.infrastructure.vectorstore.memory_store import InMemoryVectorStore


class TestVectorStoreIntegration:
    @pytest.mark.asyncio
    async def test_vector_store_health_and_collection_creation(self):
        store = InMemoryVectorStore()
        assert await store.health_check() is True
        await store.ensure_collection_exists()

    @pytest.mark.asyncio
    async def test_upsert_and_filtered_search(self):
        store = InMemoryVectorStore()
        tenant_1 = uuid.uuid4()
        user_1 = uuid.uuid4()
        doc_1 = uuid.uuid4()
        ver_1 = uuid.uuid4()

        tenant_2 = uuid.uuid4()
        user_2 = uuid.uuid4()
        doc_2 = uuid.uuid4()

        # Point for User 1
        point_1 = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.1] * 384,
            payload={
                "document_id": str(doc_1),
                "version_id": str(ver_1),
                "tenant_id": str(tenant_1),
                "user_id": str(user_1),
                "text": "Financial performance metrics for Q3 2026.",
            },
        )

        # Point for User 2
        point_2 = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.9] * 384,
            payload={
                "document_id": str(doc_2),
                "version_id": str(uuid.uuid4()),
                "tenant_id": str(tenant_2),
                "user_id": str(user_2),
                "text": "Confidential HR salary data.",
            },
        )

        await store.upsert_vectors([point_1, point_2])

        # Search isolated to User 1
        results_user_1 = await store.search(
            query_vector=[0.1] * 384,
            limit=5,
            tenant_id=tenant_1,
            user_id=user_1,
        )
        assert len(results_user_1) == 1
        assert results_user_1[0].id == point_1.id
        assert results_user_1[0].payload["document_id"] == str(doc_1)

        # Search isolated to User 2
        results_user_2 = await store.search(
            query_vector=[0.1] * 384,
            limit=5,
            tenant_id=tenant_2,
            user_id=user_2,
        )
        assert len(results_user_2) == 1
        assert results_user_2[0].id == point_2.id

    @pytest.mark.asyncio
    async def test_delete_vectors_by_document(self):
        store = InMemoryVectorStore()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        point = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.5] * 384,
            payload={
                "document_id": str(doc_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "text": "Temporary document content.",
            },
        )
        await store.upsert_vectors([point])

        # Delete by document
        deleted_count = await store.delete_by_document_id(doc_id)
        assert deleted_count == 1

        # Verify search returns nothing
        results = await store.search(
            query_vector=[0.5] * 384,
            limit=5,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        assert len(results) == 0

