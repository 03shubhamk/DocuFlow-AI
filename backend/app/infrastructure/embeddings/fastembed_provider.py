"""
DocuFlow AI — FastEmbed ONNX Local Embedding Provider.

High-throughput, CPU-optimized local embeddings powered by Qdrant FastEmbed.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.infrastructure.embeddings.base import EmbeddingProvider

logger = structlog.get_logger(__name__)


class FastEmbedProvider(EmbeddingProvider):
    """FastEmbed local ONNX runtime embedding provider."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        dimension: int = 384,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model: Any = None
        self._init_error: Exception | None = None

    @property
    def provider_name(self) -> str:
        return "fastembed"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_model(self) -> Any:
        if self._model is None and self._init_error is None:
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(model_name=self._model_name)
            except Exception as e:
                logger.warning("fastembed_load_failed_using_mock_fallback", error=str(e))
                self._init_error = e
        return self._model

    def embed_text(self, text: str) -> list[float]:
        model = self._get_model()
        if model is not None:
            try:
                embeddings = list(model.embed([text]))
                return [float(x) for x in embeddings[0]]
            except Exception as e:
                logger.error("fastembed_inference_failed", error=str(e))

        # Fallback to mock vector
        from app.infrastructure.embeddings.mock_provider import MockEmbeddingProvider

        mock = MockEmbeddingProvider(model_name=self._model_name, dimension=self._dimension)
        return mock.embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        if model is not None:
            try:
                embeddings = list(model.embed(texts))
                return [[float(x) for x in emb] for emb in embeddings]
            except Exception as e:
                logger.error("fastembed_batch_inference_failed", error=str(e))

        from app.infrastructure.embeddings.mock_provider import MockEmbeddingProvider

        mock = MockEmbeddingProvider(model_name=self._model_name, dimension=self._dimension)
        return mock.embed_batch(texts)
