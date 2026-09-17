"""
DocuFlow AI — Vector Store Module.

Provides singleton factory and interface for vector database storage.
"""

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.vectorstore.base import SearchResult, VectorPoint, VectorStore
from app.infrastructure.vectorstore.memory_store import InMemoryVectorStore
from app.infrastructure.vectorstore.qdrant_store import QdrantVectorStore


@lru_cache
def get_vector_store() -> VectorStore:
    """Return configured VectorStore singleton.

    Switches to InMemoryVectorStore in testing environment.
    """
    settings = get_settings()

    if settings.environment == "testing":
        return InMemoryVectorStore()

    return QdrantVectorStore()


__all__ = [
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "SearchResult",
    "VectorPoint",
    "VectorStore",
    "get_vector_store",
]
