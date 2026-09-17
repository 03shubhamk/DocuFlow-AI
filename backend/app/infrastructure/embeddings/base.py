"""
DocuFlow AI — Embedding Provider Interface.

Defines the abstract base class for vector embedding generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The provider identifier (e.g., 'fastembed', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The identifier/name of the embedding model."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the generated vector representation."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate vector embedding for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of text strings."""
        pass
