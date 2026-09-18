"""
DocuFlow AI — Unit Tests for Search Strategies and SearchService.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.embeddings.service import EmbeddingService
from app.application.search.schemas import SearchRequest
from app.application.search.service import SearchService
from app.application.search.strategies import (
    DenseSearchStrategy,
    HybridSearchStrategy,
)
from app.domain.entities import User, UserRole
from app.infrastructure.embeddings.mock_provider import MockEmbeddingProvider
from app.infrastructure.vectorstore.base import VectorPoint
from app.infrastructure.vectorstore.memory_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_dense_search_strategy() -> None:
    store = InMemoryVectorStore()
    doc_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    p1 = VectorPoint(
        id=uuid.uuid4(),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload={
            "document_id": str(doc_id),
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "text": "Machine learning architectures",
        },
    )
    p2 = VectorPoint(
        id=uuid.uuid4(),
        vector=[0.0, 1.0, 0.0, 0.0],
        payload={
            "document_id": str(doc_id),
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "text": "Database indexing techniques",
        },
    )
    await store.upsert_vectors([p1, p2])

    strategy = DenseSearchStrategy()
    assert strategy.strategy_name == "dense"

    results = await strategy.execute(
        query="Machine learning",
        query_vector=[1.0, 0.0, 0.0, 0.0],
        top_k=2,
        filter_criteria={},
        tenant_id=tenant_id,
        user_id=user_id,
        score_threshold=0.5,
        vector_store=store,
    )

    assert len(results) == 1
    assert results[0].id == p1.id
    assert results[0].score > 0.99


@pytest.mark.asyncio
async def test_hybrid_search_strategy_rrf() -> None:
    store = InMemoryVectorStore()
    doc_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    p1 = VectorPoint(
        id=uuid.uuid4(),
        vector=[0.8, 0.2, 0.0, 0.0],
        payload={
            "document_id": str(doc_id),
            "tenant_id": str(tenant_id),
            "text": "The quick brown fox jumps over the lazy dog",
        },
    )
    p2 = VectorPoint(
        id=uuid.uuid4(),
        vector=[0.7, 0.3, 0.0, 0.0],
        payload={
            "document_id": str(doc_id),
            "tenant_id": str(tenant_id),
            "text": "Quarterly operating revenue report and financials",
        },
    )
    await store.upsert_vectors([p1, p2])

    strategy = HybridSearchStrategy(dense_weight=0.7, sparse_weight=0.3)
    assert strategy.strategy_name == "hybrid"

    # Lexical match for "revenue financials" should boost p2
    results = await strategy.execute(
        query="operating revenue financials",
        query_vector=[0.8, 0.2, 0.0, 0.0],
        top_k=2,
        filter_criteria={},
        tenant_id=tenant_id,
        user_id=None,
        score_threshold=0.0,
        vector_store=store,
    )

    assert len(results) == 2
    assert results[0].id == p2.id


@pytest.mark.asyncio
async def test_search_service_ownership_enforcement() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    store = InMemoryVectorStore()
    embedding_provider = MockEmbeddingProvider(dimension=4)
    embedding_service = EmbeddingService(provider=embedding_provider)

    tenant_id = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    p1 = VectorPoint(
        id=uuid.uuid4(),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload={
            "document_id": str(doc1_id),
            "chunk_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "user_id": str(user1_id),
            "filename": "user1_doc.pdf",
            "text": "Confidential financial data of user 1",
            "page_number": 1,
            "section_path": "Finances",
        },
    )
    p2 = VectorPoint(
        id=uuid.uuid4(),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload={
            "document_id": str(doc2_id),
            "chunk_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "user_id": str(user2_id),
            "filename": "user2_doc.pdf",
            "text": "Confidential financial data of user 2",
            "page_number": 1,
            "section_path": "Finances",
        },
    )
    await store.upsert_vectors([p1, p2])

    service = SearchService(
        session=session,
        vector_store=store,
        embedding_service=embedding_service,
    )

    user1 = User(
        id=user1_id,
        tenant_id=tenant_id,
        email="user1@example.com",
        hashed_password="hashed_pw_1",
        full_name="User One",
        role=UserRole.USER,
    )
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.com",
        hashed_password="hashed_pw_admin",
        full_name="Admin User",
        role=UserRole.ADMIN,
    )

    # Regular user 1 search should only return user 1 document
    req = SearchRequest(query="financial data", top_k=10)
    res_user1 = await service.search(request=req, current_user=user1)
    assert len(res_user1.results) == 1
    assert res_user1.results[0].document_id == doc1_id

    # Admin search should return both documents in tenant
    res_admin = await service.search(request=req, current_user=admin)
    assert len(res_admin.results) == 2


@pytest.mark.asyncio
async def test_search_service_score_threshold_and_document_filter() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    store = InMemoryVectorStore()
    embedding_provider = MockEmbeddingProvider(dimension=4)
    embedding_service = EmbeddingService(provider=embedding_provider)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    p1 = VectorPoint(
        id=uuid.uuid4(),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload={
            "document_id": str(doc_id),
            "chunk_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "filename": "annual_report.pdf",
            "text": "Executive summary with 99% relevance",
            "page_number": 1,
        },
    )
    await store.upsert_vectors([p1])

    # Mock document repo get_by_id_scoped
    service = SearchService(
        session=session,
        vector_store=store,
        embedding_service=embedding_service,
    )
    mock_doc = MagicMock(id=doc_id, title="Annual Report")
    service.document_repo.get_by_id_scoped = AsyncMock(return_value=mock_doc)

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="user@example.com",
        hashed_password="hashed_pw_user",
        full_name="Test User",
        role=UserRole.USER,
    )

    # Search with accessible document_ids filter
    req_doc = SearchRequest(query="Executive summary", top_k=5, document_ids=[doc_id])
    res_doc = await service.search(request=req_doc, current_user=user)
    assert len(res_doc.results) == 1
    assert res_doc.results[0].document_name == "annual_report.pdf"

    # Search with inaccessible document_ids filter (returns empty)
    service.document_repo.get_by_id_scoped = AsyncMock(return_value=None)
    req_inaccessible = SearchRequest(query="Executive summary", top_k=5, document_ids=[uuid.uuid4()])
    res_inaccessible = await service.search(request=req_inaccessible, current_user=user)
    assert len(res_inaccessible.results) == 0
