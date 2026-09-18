"""
DocuFlow AI — In-Memory Vector Store.

Fast, deterministic in-memory vector store for unit tests, offline development,
and CI environments without requiring external Docker Qdrant instances.
"""

from __future__ import annotations

import math
import uuid
from typing import Any

from app.infrastructure.vectorstore.base import SearchResult, VectorPoint, VectorStore


class InMemoryVectorStore(VectorStore):
    """In-memory vector store with cosine similarity search and payload filtering."""

    def __init__(
        self,
        collection_name: str | None = None,
        dimension: int | None = None,
        distance: str | None = None,
    ) -> None:
        self.collection_name = collection_name or "docuflow_chunks"
        self.dimension = dimension or 384
        self.distance = distance or "Cosine"
        self.points: dict[uuid.UUID, VectorPoint] = {}
        self.collection_created: bool = False
        self.payload_indexes: set[str] = set()

    async def count(self, tenant_id: uuid.UUID | None = None) -> int:
        """Count total indexed points, optionally filtered by tenant."""
        if tenant_id is None:
            return len(self.points)
        return sum(1 for p in self.points.values() if str(p.payload.get("tenant_id")) == str(tenant_id))

    async def ensure_collection_exists(self) -> None:
        self.collection_created = True

    async def create_payload_indexes(self) -> None:
        self.payload_indexes.update([
            "document_id",
            "version_id",
            "tenant_id",
            "user_id",
            "chunk_id",
            "page_number",
            "chunk_index",
        ])

    async def upsert_vectors(self, points: list[VectorPoint]) -> int:
        for p in points:
            self.points[p.id] = p
        return len(points)

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        to_delete = [
            pid for pid, pt in self.points.items()
            if str(pt.payload.get("document_id")) == str(document_id)
        ]
        for pid in to_delete:
            del self.points[pid]
        return len(to_delete)

    async def delete_by_version_id(self, version_id: uuid.UUID) -> int:
        to_delete = [
            pid for pid, pt in self.points.items()
            if str(pt.payload.get("version_id")) == str(version_id)
        ]
        for pid in to_delete:
            del self.points[pid]
        return len(to_delete)

    @staticmethod
    def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2, strict=True))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 <= 0 or norm2 <= 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_criteria: dict[str, Any] | None = None,
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        scored_results: list[SearchResult] = []

        filters = dict(filter_criteria or {})
        if tenant_id is not None:
            filters["tenant_id"] = str(tenant_id)
        if user_id is not None:
            filters["user_id"] = str(user_id)

        for pid, pt in self.points.items():
            # Check filter criteria
            if filters:
                match = True
                for k, v in filters.items():
                    if v is None:
                        continue
                    if k == "document_ids" and isinstance(v, (list, set, tuple)):
                        doc_id_val = str(pt.payload.get("document_id", ""))
                        if doc_id_val not in [str(item) for item in v]:
                            match = False
                            break
                    elif k == "page_number":
                        page_num = pt.payload.get("page_number")
                        page_nums = pt.payload.get("page_numbers", [])
                        if page_num != v and v not in page_nums:
                            match = False
                            break
                    elif str(pt.payload.get(k)) != str(v):
                        match = False
                        break
                if not match:
                    continue

            score = self._cosine_similarity(query_vector, pt.vector)
            scored_results.append(SearchResult(id=pid, score=score, payload=pt.payload))

        # Sort descending by score
        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:limit]

    async def get_point(self, point_id: uuid.UUID) -> VectorPoint | None:
        return self.points.get(point_id)

    async def health_check(self) -> bool:
        return True

    def clear(self) -> None:
        """Reset the in-memory store."""
        self.points.clear()
