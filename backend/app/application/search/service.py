"""
DocuFlow AI — Search Application Service.

Orchestrates multi-tenant semantic vector search and hybrid retrieval with
ownership enforcement, payload filtering, document resolution, and audit logging.
"""

from __future__ import annotations

import time
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.embeddings.service import EmbeddingService
from app.application.search.qa_service import QAService
from app.application.search.schemas import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.application.search.strategies import (
    DenseSearchStrategy,
    HybridSearchStrategy,
    SearchStrategy,
)
from app.config import get_settings
from app.domain.entities import User, UserRole
from app.infrastructure.database.repositories import (
    AuditLogRepository,
    DocumentRepository,
)
from app.infrastructure.vectorstore import get_vector_store
from app.infrastructure.vectorstore.base import VectorStore

logger = structlog.get_logger(__name__)


class SearchService:
    """Service layer managing secure, isolated document search, RAG synthesis, and ranking."""

    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
        dense_strategy: SearchStrategy | None = None,
        hybrid_strategy: SearchStrategy | None = None,
        qa_service: QAService | None = None,
    ) -> None:
        self.session = session
        self.settings = get_settings()
        self.vector_store = vector_store or get_vector_store()
        self.embedding_service = embedding_service or EmbeddingService()
        self.dense_strategy = dense_strategy or DenseSearchStrategy()
        self.hybrid_strategy = hybrid_strategy or HybridSearchStrategy(
            dense_weight=self.settings.search_hybrid_dense_weight,
            sparse_weight=self.settings.search_hybrid_sparse_weight,
        )
        self.qa_service = qa_service or QAService()
        self.document_repo = DocumentRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def _ensure_hydrated(self) -> None:
        """Ensure vector store has points loaded from SQLite if running in memory store."""
        try:
            count = await self.vector_store.count()
            if count == 0:
                from sqlalchemy import select
                from app.infrastructure.database.models import DocumentModel, DocumentChunkModel
                from app.infrastructure.vectorstore.base import VectorPoint

                docs = (await self.session.execute(select(DocumentModel))).scalars().all()
                for doc in docs:
                    chunks = (await self.session.execute(
                        select(DocumentChunkModel).where(DocumentChunkModel.document_id == doc.id)
                    )).scalars().all()
                    if not chunks:
                        continue
                    texts = [c.content for c in chunks]
                    embeddings = await self.embedding_service.generate_embeddings(texts)
                    points = []
                    for c, emb in zip(chunks, embeddings):
                        pt_id = uuid.uuid4()
                        payload = {
                            "document_id": str(doc.id),
                            "version_id": str(c.version_id) if c.version_id else "",
                            "tenant_id": str(doc.tenant_id),
                            "user_id": str(doc.owner_id) if doc.owner_id else "",
                            "chunk_id": str(c.id),
                            "chunk_index": c.chunk_index,
                            "filename": doc.original_filename or doc.title or "Document",
                            "mime_type": doc.file_type or "application/pdf",
                            "text": c.content,
                            "token_count": c.token_count,
                            "page_number": c.page_numbers[0] if c.page_numbers else 1,
                            "page_numbers": c.page_numbers or [],
                            "heading_hierarchy": c.heading_hierarchy or [],
                            "section_path": c.heading_hierarchy[-1] if c.heading_hierarchy else None,
                        }
                        points.append(VectorPoint(id=pt_id, vector=emb, payload=payload))
                    await self.vector_store.upsert_vectors(points)
        except Exception as exc:
            logger.warning("vector_store_auto_hydrate_failed", error=str(exc))

    async def search(
        self,
        request: SearchRequest,
        current_user: User,
    ) -> SearchResponse:
        """Execute semantic or hybrid search with multi-tenant isolation and metadata filtering."""
        start_time = time.perf_counter()
        logger.info(
            "search_query_received",
            query=request.query,
            user_id=str(current_user.id),
            tenant_id=str(current_user.tenant_id),
            role=current_user.role.value,
        )

        # 1. Enforce ownership and tenant isolation
        tenant_id = current_user.tenant_id
        user_id = None if current_user.role == UserRole.ADMIN else current_user.id

        # 2. If specific document_ids are supplied, verify tenant & ownership accessibility
        filter_doc_ids: list[str] = []
        if request.document_ids:
            for doc_id in request.document_ids:
                doc = await self.document_repo.get_by_id_scoped(
                    document_id=doc_id,
                    tenant_id=tenant_id,
                    owner_id=user_id,
                )
                if doc is not None:
                    filter_doc_ids.append(str(doc.id))

            # If user requested document_ids but none are accessible, return empty immediately
            if not filter_doc_ids:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return SearchResponse(
                    results=[],
                    total=0,
                    query=request.query,
                    top_k=request.top_k,
                    strategy_used="dense",
                    duration_ms=duration_ms,
                )

        # 3. Ensure vector store is hydrated
        await self._ensure_hydrated()

        # 4. Construct filter criteria
        filter_criteria = dict(request.filters or {})
        if filter_doc_ids:
            filter_criteria["document_ids"] = filter_doc_ids
        if request.page is not None:
            filter_criteria["page_number"] = request.page

        # 4. Generate query embedding
        query_embeddings = await self.embedding_service.generate_embeddings([request.query])
        query_vector = query_embeddings[0] if query_embeddings else []

        # 5. Select execution strategy
        strategy_name = request.strategy.lower() if request.strategy else None
        if strategy_name == "hybrid" or (strategy_name is None and self.settings.search_hybrid_enabled):
            active_strategy = self.hybrid_strategy
        else:
            active_strategy = self.dense_strategy

        # 6. Execute retrieval
        score_threshold = (
            request.score_threshold
            if request.score_threshold is not None
            else self.settings.search_default_score_threshold
        )
        top_k = request.top_k or self.settings.search_default_top_k

        raw_results = await active_strategy.execute(
            query=request.query,
            query_vector=query_vector,
            top_k=top_k,
            filter_criteria=filter_criteria,
            tenant_id=tenant_id,
            user_id=user_id,
            score_threshold=score_threshold,
            vector_store=self.vector_store,
        )

        # 7. Map to serialized SearchResultItems
        results: list[SearchResultItem] = []
        for res in raw_results:
            payload = res.payload or {}
            chunk_id_raw = payload.get("chunk_id")
            doc_id_raw = payload.get("document_id")

            chunk_id = uuid.UUID(str(chunk_id_raw)) if chunk_id_raw else res.id
            document_id = uuid.UUID(str(doc_id_raw)) if doc_id_raw else uuid.uuid4()
            document_name = payload.get("filename") or "Document"

            item = SearchResultItem(
                chunk_id=chunk_id,
                document_id=document_id,
                document_name=document_name,
                score=round(res.score, 4),
                text=str(payload.get("text", "")),
                page_number=payload.get("page_number"),
                page_numbers=payload.get("page_numbers") or [],
                section=payload.get("section_path"),
                heading_hierarchy=payload.get("heading_hierarchy") or [],
                chunk_index=payload.get("chunk_index", 0),
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k not in {"text", "document_id", "chunk_id", "filename", "section_path", "heading_hierarchy"}
                },
            )
            results.append(item)

        # 8. Pagination handling if page_size is specified
        total = len(results)
        paginated_results = results
        page_num = None
        page_size_val = None

        if request.page_size is not None:
            page_size_val = request.page_size
            page_num = request.page or 1
            offset = (page_num - 1) * page_size_val
            paginated_results = results[offset : offset + page_size_val]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 9. Audit logging
        await self.audit_repo.log_action(
            tenant_id=tenant_id,
            user_id=current_user.id,
            action="SEARCH_QUERY",
            resource_type="search",
            details={
                "query": request.query,
                "strategy": active_strategy.strategy_name,
                "results_count": len(paginated_results),
                "duration_ms": duration_ms,
            },
        )
        await self.session.commit()

        logger.info(
            "search_query_completed",
            results_count=len(paginated_results),
            strategy=active_strategy.strategy_name,
            duration_ms=duration_ms,
        )

        # 10. Generate synthesized natural language AI answer and citations
        qa_output = self.qa_service.generate_answer(
            query=request.query,
            results=results,
        )

        return SearchResponse(
            results=paginated_results,
            total=total,
            query=request.query,
            top_k=top_k,
            page=page_num,
            page_size=page_size_val,
            strategy_used=active_strategy.strategy_name,
            duration_ms=duration_ms,
            ai_answer=qa_output.answer,
            citations=qa_output.citations,
        )

    async def chat(
        self,
        request: ChatRequest,
        current_user: User,
    ) -> ChatResponse:
        """Process a conversational chat query grounded in accessible document knowledge."""
        if not request.messages:
            return ChatResponse(
                message="Please ask a question about your documents.",
                citations=[],
                confidence=0.0,
                source_chunks_count=0,
            )

        latest_user_query = request.messages[-1].content

        # Retrieve relevant context
        search_req = SearchRequest(
            query=latest_user_query,
            top_k=request.top_k,
            document_ids=request.document_ids,
        )
        search_res = await self.search(search_req, current_user)

        return self.qa_service.generate_chat_response(
            messages=request.messages,
            results=search_res.results,
        )
