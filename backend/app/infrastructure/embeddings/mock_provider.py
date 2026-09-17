"""
DocuFlow AI — Mock Embedding Provider.

Generates deterministic, unit-normalized pseudo-random vectors for fast, lightweight testing
and offline development without downloading multi-gigabyte neural network models.
"""

from __future__ import annotations

import hashlib
import math
import struct

from app.infrastructure.embeddings.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, zero-dependency embedding provider for tests and development."""

    def __init__(
        self,
        model_name: str = "mock-embedding-v1",
        dimension: int = 384,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_to_vector(self, text: str) -> list[float]:
        """Convert a text string to a deterministic unit-normalized float vector."""
        if not text:
            return [0.0] * self._dimension

        vec: list[float] = []
        seed = 0
        while len(vec) < self._dimension:
            # Generate deterministic floats from chained SHA-256 hashes
            h = hashlib.sha256(f"{text}:{seed}:{self._model_name}".encode("utf-8")).digest()
            # Unpack into 8 floats (4 bytes each)
            floats = [struct.unpack("f", h[i : i + 4])[0] for i in range(0, 32, 4)]
            # Clean non-finite values if any
            for f in floats:
                val = f if math.isfinite(f) else 0.5
                vec.append(val)
                if len(vec) == self._dimension:
                    break
            seed += 1

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [round(x / norm, 6) for x in vec]
        return vec

    def embed_text(self, text: str) -> list[float]:
        return self._hash_to_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]
