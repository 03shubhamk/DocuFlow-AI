"""
DocuFlow AI — Unit Tests for Embedding Providers and EmbeddingService.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.embeddings.service import EmbeddingService
from app.infrastructure.chunking.base import ChunkData
from app.infrastructure.embeddings.fastembed_provider import FastEmbedProvider
from app.infrastructure.embeddings.mock_provider import MockEmbeddingProvider


@pytest.mark.asyncio
async def test_mock_embedding_provider_deterministic() -> None:
    provider = MockEmbeddingProvider(dimension=384, model_name="test-mock-v1")
    assert provider.provider_name == "mock"
    assert provider.dimension == 384
    assert provider.model_name == "test-mock-v1"

    texts = ["Hello world", "DocuFlow AI Vector Search", "Hello world"]
    vectors = provider.embed_batch(texts)

    assert len(vectors) == 3
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
    # Identical texts must produce identical deterministic vectors
    assert vectors[0] == vectors[2]
    assert vectors[0] != vectors[1]

    # Query embedding
    query_vec = provider.embed_text("Hello world")
    assert query_vec == vectors[0]


@pytest.mark.asyncio
async def test_embedding_service_batching() -> None:
    provider = MockEmbeddingProvider(dimension=128)
    service = EmbeddingService(provider=provider, batch_size=2)

    assert service.dimension == 128
    assert service.model_name == provider.model_name

    texts = [f"Text chunk number {i}" for i in range(5)]
    vectors = await service.generate_embeddings(texts)

    assert len(vectors) == 5
    for vec in vectors:
        assert len(vec) == 128

    # Empty batch
    empty_vectors = await service.generate_embeddings([])
    assert empty_vectors == []


@pytest.mark.asyncio
async def test_embedding_service_chunk_models() -> None:
    provider = MockEmbeddingProvider(dimension=64)
    service = EmbeddingService(provider=provider)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    chunks = [
        ChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            version_id=ver_id,
            text=f"Sample chunk text {i}",
            token_count=10 + i,
            chunk_index=i,
            page_numbers=[1],
        )
        for i in range(3)
    ]

    vectors = await service.generate_chunk_embeddings(chunks)
    assert len(vectors) == 3
    for _chunk_id, vec in vectors:
        assert len(vec) == 64


def test_fastembed_provider_properties() -> None:
    provider = FastEmbedProvider(model_name="BAAI/bge-small-en-v1.5", dimension=384)
    assert provider.provider_name == "fastembed"
    assert provider.model_name == "BAAI/bge-small-en-v1.5"
    assert provider.dimension == 384
