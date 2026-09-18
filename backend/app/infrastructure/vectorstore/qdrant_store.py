"""
DocuFlow AI — Qdrant Vector Store Implementation.

Implements the VectorStore interface using the official QdrantClient SDK.
Manages collection lifecycle, payload indexes, idempotent upserts, filtering, and deletions.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from app.config import get_settings
from app.infrastructure.vectorstore.base import SearchResult, VectorPoint, VectorStore

logger = structlog.get_logger(__name__)


class QdrantVectorStore(VectorStore):
    """Production vector store implementation backed by Qdrant."""

    def __init__(
        self,
        collection_name: str | None = None,
        dimension: int | None = None,
        distance: str | None = None,
        client: Any = None,
    ) -> None:
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.qdrant_collection_name
        self.dimension = dimension or self.settings.embedding_dimension
        self.distance = distance or self.settings.qdrant_distance
        self._client: Any = client

    def _get_client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient

            if self.settings.qdrant_url:
                self._client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key,
                )
            else:
                self._client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                    api_key=self.settings.qdrant_api_key,
                )
        return self._client

    async def ensure_collection_exists(self) -> None:
        """Create the target collection if it does not already exist."""
        client = self._get_client()

        def _sync_ensure() -> None:
            from qdrant_client.http import models

            distance_enum = getattr(models.Distance, self.distance.upper(), models.Distance.COSINE)
            if hasattr(client, "collection_exists"):
                exists = client.collection_exists(self.collection_name)
            else:
                collections = client.get_collections().collections
                exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info(
                    "creating_qdrant_collection",
                    collection=self.collection_name,
                    dimension=self.dimension,
                    distance=self.distance,
                )
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.dimension,
                        distance=distance_enum,
                    ),
                )

        await asyncio.to_thread(_sync_ensure)
        await self.create_payload_indexes()

    async def create_payload_indexes(self) -> None:
        """Create payload indexes on frequently filtered fields."""
        client = self._get_client()

        def _sync_indexes() -> None:
            from qdrant_client.http import models

            keyword_fields = [
                "document_id",
                "version_id",
                "tenant_id",
                "user_id",
                "chunk_id",
                "mime_type",
            ]
            integer_fields = ["page_number", "chunk_index"]

            for field_name in keyword_fields:
                try:
                    client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

            for field_name in integer_fields:
                try:
                    client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=models.PayloadSchemaType.INTEGER,
                    )
                except Exception:
                    pass

        await asyncio.to_thread(_sync_indexes)

    async def upsert_vectors(self, points: list[VectorPoint]) -> int:
        """Upsert a list of vector points into the collection."""
        if not points:
            return 0

        await self.ensure_collection_exists()
        client = self._get_client()

        def _sync_upsert() -> int:
            from qdrant_client.http import models

            qdrant_points = [
                models.PointStruct(
                    id=str(p.id),
                    vector=p.vector,
                    payload=p.payload,
                )
                for p in points
            ]
            client.upsert(
                collection_name=self.collection_name,
                points=qdrant_points,
                wait=True,
            )
            return len(qdrant_points)

        return await asyncio.to_thread(_sync_upsert)

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        """Delete all points matching a document ID."""
        client = self._get_client()

        def _sync_delete() -> int:
            from qdrant_client.http import models

            client.delete(
                collection_name=self.collection_name,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                ),
                wait=True,
            )
            return 1

        try:
            return await asyncio.to_thread(_sync_delete)
        except Exception as e:
            logger.warning("qdrant_delete_by_doc_warning", document_id=str(document_id), error=str(e))
            return 0

    async def delete_by_version_id(self, version_id: uuid.UUID) -> int:
        """Delete all points matching a document version ID."""
        client = self._get_client()

        def _sync_delete() -> int:
            from qdrant_client.http import models

            client.delete(
                collection_name=self.collection_name,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(value=str(version_id)),
                        )
                    ]
                ),
                wait=True,
            )
            return 1

        try:
            return await asyncio.to_thread(_sync_delete)
        except Exception as e:
            logger.warning("qdrant_delete_by_version_warning", version_id=str(version_id), error=str(e))
            return 0

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_criteria: dict[str, Any] | None = None,
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        """Perform semantic similarity search with optional metadata filtering."""
        client = self._get_client()

        def _sync_search() -> list[SearchResult]:
            from qdrant_client.http import models

            filters = dict(filter_criteria or {})
            if tenant_id is not None:
                filters["tenant_id"] = str(tenant_id)
            if user_id is not None:
                filters["user_id"] = str(user_id)

            query_filter = None
            if filters:
                conditions: list[Any] = []
                for key, val in filters.items():
                    if val is not None:
                        if isinstance(val, (list, tuple, set)):
                            conditions.append(
                                models.FieldCondition(
                                    key="document_id",
                                    match=models.MatchAny(any=[str(x) for x in val]),
                                )
                            )
                        else:
                            conditions.append(
                                models.FieldCondition(
                                    key=key,
                                    match=models.MatchValue(value=str(val)),
                                )
                            )
                if conditions:
                    query_filter = models.Filter(must=conditions)

            hits = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )

            return [
                SearchResult(
                    id=uuid.UUID(h.id) if isinstance(h.id, str) else h.id,
                    score=float(h.score),
                    payload=h.payload or {},
                )
                for h in hits
            ]

        try:
            return await asyncio.to_thread(_sync_search)
        except Exception as e:
            logger.error("qdrant_search_failed", error=str(e))
            return []

    async def get_point(self, point_id: uuid.UUID) -> VectorPoint | None:
        """Fetch a specific vector point by UUID."""
        client = self._get_client()

        def _sync_get() -> VectorPoint | None:
            records = client.retrieve(
                collection_name=self.collection_name,
                ids=[str(point_id)],
                with_vectors=True,
                with_payload=True,
            )
            if not records:
                return None
            rec = records[0]
            return VectorPoint(
                id=uuid.UUID(rec.id) if isinstance(rec.id, str) else rec.id,
                vector=rec.vector if isinstance(rec.vector, list) else [],
                payload=rec.payload or {},
            )

        try:
            return await asyncio.to_thread(_sync_get)
        except Exception:
            return None

    async def health_check(self) -> bool:
        """Verify connectivity to Qdrant."""
        client = self._get_client()

        def _sync_health() -> bool:
            try:
                client.get_collections()
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_sync_health)
