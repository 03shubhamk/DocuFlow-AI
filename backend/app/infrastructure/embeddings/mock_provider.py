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
        """Convert a text string to a deterministic unit-normalized float vector with token semantics."""
        if not text:
            return [0.0] * self._dimension

        import re

        tokens = [w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 1]

        def _raw_hash(t: str) -> list[float]:
            vec: list[float] = []
            seed = 0
            while len(vec) < self._dimension:
                h = hashlib.sha256(f"{t}:{seed}:{self._model_name}".encode("utf-8")).digest()
                floats = [struct.unpack("f", h[i : i + 4])[0] for i in range(0, 32, 4)]
                for f in floats:
                    val = f if math.isfinite(f) else 0.5
                    vec.append(val)
                    if len(vec) == self._dimension:
                        break
                seed += 1
            return vec

        combined = _raw_hash(text)
        for tok in tokens:
            t_vec = _raw_hash(tok)
            for i in range(self._dimension):
                combined[i] += t_vec[i] * 2.0

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in combined))
        if norm > 0:
            return [round(x / norm, 6) for x in combined]
        return combined

    def embed_text(self, text: str) -> list[float]:
        return self._hash_to_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]
