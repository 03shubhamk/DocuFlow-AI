"""
DocuFlow AI — Embeddings Module.

Provides singleton factory and abstractions for embedding generation.
"""

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.embeddings.base import EmbeddingProvider
from app.infrastructure.embeddings.fastembed_provider import FastEmbedProvider
from app.infrastructure.embeddings.mock_provider import MockEmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Return configured embedding provider singleton.

    Switches to MockEmbeddingProvider in testing environment to prevent heavy downloads.
    """
    settings = get_settings()

    if settings.environment == "testing" or settings.embedding_provider == "mock":
        return MockEmbeddingProvider(
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    return FastEmbedProvider(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )


__all__ = [
    "EmbeddingProvider",
    "FastEmbedProvider",
    "MockEmbeddingProvider",
    "get_embedding_provider",
]
