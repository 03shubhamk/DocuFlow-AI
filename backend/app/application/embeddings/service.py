"""
DocuFlow AI — Application Embedding Service.

Orchestrates batch vector generation for document chunks using the configured EmbeddingProvider.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.config import get_settings
from app.infrastructure.embeddings import EmbeddingProvider, get_embedding_provider

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service managing vector embedding generation for document chunks."""

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.provider = provider or get_embedding_provider()
        self.settings = get_settings()
        self.batch_size = batch_size or self.settings.embedding_batch_size

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector representations for a list of raw text strings in batches."""
        if not texts:
            return []

        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = self.provider.embed_batch(batch)
            results.extend(vectors)
        return results

    async def generate_chunk_embeddings(
        self,
        chunks: list[Any],
    ) -> list[tuple[uuid.UUID, list[float]]]:
        """Generate vector representations for a list of chunk entities in batches.

        Returns list of tuples (chunk_id, vector).
        """
        if not chunks:
            return []

        results: list[tuple[uuid.UUID, list[float]]] = []

        logger.info(
            "generating_embeddings_start",
            chunk_count=len(chunks),
            model=self.provider.model_name,
            dimension=self.provider.dimension,
        )

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [getattr(c, "content", getattr(c, "text", "")) for c in batch]
            vectors = self.provider.embed_batch(texts)

            for chunk, vec in zip(batch, vectors, strict=True):
                chunk_id = getattr(chunk, "id", getattr(chunk, "chunk_id", None))
                if chunk_id is not None:
                    results.append((chunk_id, vec))

        logger.info("generating_embeddings_completed", count=len(results))
        return results
