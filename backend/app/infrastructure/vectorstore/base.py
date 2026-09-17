"""
DocuFlow AI — Vector Store Core Interfaces and DTOs.

Defines the abstract interface for vector database storage and similarity search.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorPoint:
    """Represents a vector point stored in the vector database with its metadata payload."""

    id: uuid.UUID
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Represents a vector similarity search match."""

    id: uuid.UUID
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """Abstract interface for vector database storage (e.g. Qdrant)."""

    @abstractmethod
    async def ensure_collection_exists(self) -> None:
        """Create the vector collection if it does not exist."""
        pass

    @abstractmethod
    async def create_payload_indexes(self) -> None:
        """Create payload indexes on frequently filtered fields."""
        pass

    @abstractmethod
    async def upsert_vectors(self, points: list[VectorPoint]) -> int:
        """Upsert a list of vector points and payloads."""
        pass

    @abstractmethod
    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        """Delete all vector points belonging to a specific document."""
        pass

    @abstractmethod
    async def delete_by_version_id(self, version_id: uuid.UUID) -> int:
        """Delete all vector points belonging to a specific document version."""
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_criteria: dict[str, Any] | None = None,
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        """Perform semantic similarity search with metadata filtering."""
        pass

    @abstractmethod
    async def get_point(self, point_id: uuid.UUID) -> VectorPoint | None:
        """Retrieve a vector point by its UUID."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check connection health with the vector database."""
        pass
