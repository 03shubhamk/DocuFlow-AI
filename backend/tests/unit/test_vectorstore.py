"""
DocuFlow AI — Unit Tests for Vector Stores (InMemoryVectorStore and QdrantVectorStore).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.infrastructure.vectorstore.base import VectorPoint
from app.infrastructure.vectorstore.memory_store import InMemoryVectorStore
from app.infrastructure.vectorstore.qdrant_store import QdrantVectorStore


@pytest.mark.asyncio
async def test_in_memory_vector_store_crud_and_search() -> None:
    store = InMemoryVectorStore(collection_name="test_chunks", dimension=4)
    await store.ensure_collection_exists()
    assert await store.health_check() is True

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()

    points = [
        VectorPoint(
            id=p1_id,
            vector=[1.0, 0.0, 0.0, 0.0],
            payload={
                "document_id": str(doc_id),
                "version_id": str(ver_id),
                "chunk_id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "text": "Antigravity artificial intelligence research",
                "chunk_index": 0,
            },
        ),
        VectorPoint(
            id=p2_id,
            vector=[0.0, 1.0, 0.0, 0.0],
            payload={
                "document_id": str(doc_id),
                "version_id": str(ver_id),
                "chunk_id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "text": "Deep neural networks and LLMs",
                "chunk_index": 1,
            },
        ),
    ]

    # Upsert
    inserted = await store.upsert_vectors(points)
    assert inserted == 2
    assert await store.count(tenant_id=tenant_id) == 2

    # Get single point
    retrieved = await store.get_point(p1_id)
    assert retrieved is not None
    assert retrieved.id == p1_id
    assert retrieved.payload["chunk_index"] == 0

    # Search with exact query vector match
    results = await store.search(
        query_vector=[1.0, 0.0, 0.0, 0.0],
        limit=2,
        tenant_id=tenant_id,
    )
    assert len(results) == 2
    assert results[0].id == p1_id
    assert results[0].score > 0.99

    # Search with user filter
    results_user = await store.search(
        query_vector=[1.0, 0.0, 0.0, 0.0],
        limit=2,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    assert len(results_user) == 2

    # Search with wrong tenant returns empty
    results_wrong_tenant = await store.search(
        query_vector=[1.0, 0.0, 0.0, 0.0],
        limit=2,
        tenant_id=uuid.uuid4(),
    )
    assert len(results_wrong_tenant) == 0

    # Delete by version
    del_count = await store.delete_by_version_id(ver_id)
    assert del_count == 2
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_qdrant_vector_store_mocked() -> None:
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    store = QdrantVectorStore(
        collection_name="docuflow_chunks",
        dimension=384,
        distance="Cosine",
        client=mock_client,
    )

    await store.ensure_collection_exists()
    assert mock_client.collection_exists.called is True

    # Health check
    mock_client.get_collections.return_value = MagicMock(collections=[MagicMock(name="docuflow_chunks")])
    assert await store.health_check() is True

    # Upsert
    p_id = uuid.uuid4()
    points = [
        VectorPoint(
            id=p_id,
            vector=[0.1] * 384,
            payload={"document_id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4())},
        )
    ]
    upserted = await store.upsert_vectors(points)
    assert upserted == 1
    assert mock_client.upsert.called is True

    # Delete vectors
    await store.delete_by_document_id(uuid.uuid4())
    assert mock_client.delete.called is True
