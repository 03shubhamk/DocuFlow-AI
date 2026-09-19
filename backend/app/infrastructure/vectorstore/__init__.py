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

    Switches to InMemoryVectorStore in testing environment or if Qdrant is unreachable in development.
    """
    settings = get_settings()

    if settings.environment == "testing":
        return InMemoryVectorStore()

    if settings.environment == "development":
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            host = settings.qdrant_host or "127.0.0.1"
            port = settings.qdrant_port or 6333
            res = sock.connect_ex((host, port))
            sock.close()
            if res != 0:
                return InMemoryVectorStore()
        except Exception:
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
