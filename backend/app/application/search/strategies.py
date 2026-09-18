"""
DocuFlow AI — Search Strategies (Dense Semantic & Hybrid Fusion).

Implements the strategy pattern for document search:
1. DenseSearchStrategy: Pure dense cosine vector similarity search via Qdrant.
2. HybridSearchStrategy: Blends dense semantic search with sparse lexical token relevance using Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.infrastructure.vectorstore.base import SearchResult, VectorStore


class SearchStrategy(ABC):
    """Abstract base class for retrieval and ranking strategies."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Name of the strategy."""
        pass

    @abstractmethod
    async def execute(
        self,
        query: str,
        query_vector: list[float],
        top_k: int,
        filter_criteria: dict[str, Any],
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        score_threshold: float,
        vector_store: VectorStore,
    ) -> list[SearchResult]:
        """Execute retrieval and return ranked SearchResult items."""
        pass


class DenseSearchStrategy(SearchStrategy):
    """Standard dense semantic vector search powered by Qdrant cosine similarity."""

    @property
    def strategy_name(self) -> str:
        return "dense"

    async def execute(
        self,
        query: str,
        query_vector: list[float],
        top_k: int,
        filter_criteria: dict[str, Any],
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        score_threshold: float,
        vector_store: VectorStore,
    ) -> list[SearchResult]:
        # Retrieve extra candidates if threshold filtering is active
        fetch_limit = max(top_k * 2, top_k) if score_threshold > 0 else top_k

        raw_results = await vector_store.search(
            query_vector=query_vector,
            limit=fetch_limit,
            filter_criteria=filter_criteria,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        filtered = [r for r in raw_results if r.score >= score_threshold]
        return filtered[:top_k]


class HybridSearchStrategy(SearchStrategy):
    """Hybrid search blending dense vector similarity with sparse lexical token matching.

    Uses Reciprocal Rank Fusion (RRF) and weighted lexical boosting to combine dense and sparse rankings.
    """

    def __init__(
        self,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        rrf_k: int = 60,
    ) -> None:
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k

    @property
    def strategy_name(self) -> str:
        return "hybrid"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenizer for lexical matching."""
        return [w.lower() for w in re.findall(r"\b\w+\b", text) if len(w) > 1]

    def _lexical_score(self, query_tokens: list[str], text: str) -> float:
        """Calculate token-overlap BM25-style lexical relevance score."""
        if not query_tokens or not text:
            return 0.0
        doc_tokens = self._tokenize(text)
        if not doc_tokens:
            return 0.0

        doc_token_counts: dict[str, int] = {}
        for t in doc_tokens:
            doc_token_counts[t] = doc_token_counts.get(t, 0) + 1

        score = 0.0
        doc_len = len(doc_tokens)
        avg_len = 100.0  # reference average chunk token length
        k1 = 1.2
        b = 0.75

        for q in query_tokens:
            freq = doc_token_counts.get(q, 0)
            if freq > 0:
                tf = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / avg_len)))
                score += tf

        # Normalize score into a bounded range [0.0, 1.0]
        return min(1.0, score / max(1.0, len(query_tokens) * 2.0))

    async def execute(
        self,
        query: str,
        query_vector: list[float],
        top_k: int,
        filter_criteria: dict[str, Any],
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        score_threshold: float,
        vector_store: VectorStore,
    ) -> list[SearchResult]:
        # 1. Fetch dense candidates
        dense_candidates = await vector_store.search(
            query_vector=query_vector,
            limit=max(top_k * 3, 50),
            filter_criteria=filter_criteria,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        if not dense_candidates:
            return []

        # 2. Compute sparse / lexical scores for each candidate
        query_tokens = self._tokenize(query)
        scored_candidates: list[tuple[SearchResult, float]] = []

        # Sort dense ranks
        dense_ranks: dict[uuid.UUID, int] = {
            res.id: idx for idx, res in enumerate(dense_candidates)
        }

        # Lexical rank ordering
        lexical_scored = [
            (res, self._lexical_score(query_tokens, str(res.payload.get("text", ""))))
            for res in dense_candidates
        ]
        lexical_scored.sort(key=lambda x: x[1], reverse=True)
        sparse_ranks: dict[uuid.UUID, int] = {
            res.id: idx for idx, (res, _) in enumerate(lexical_scored)
        }

        # 3. Reciprocal Rank Fusion & weighted score combination
        for res, lex_score in lexical_scored:
            dense_rank = dense_ranks.get(res.id, len(dense_candidates))
            sparse_rank = sparse_ranks.get(res.id, len(dense_candidates))

            rrf_dense = 1.0 / (self.rrf_k + dense_rank + 1)
            rrf_sparse = 1.0 / (self.rrf_k + sparse_rank + 1)

            # Combined blended score
            fused_score = (self.dense_weight * res.score) + (self.sparse_weight * lex_score)
            # Apply RRF boost
            final_score = round(fused_score * 0.7 + (rrf_dense + rrf_sparse) * 10 * 0.3, 4)

            if final_score >= score_threshold:
                scored_candidates.append((
                    SearchResult(id=res.id, score=min(1.0, max(0.0, final_score)), payload=res.payload),
                    final_score,
                ))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored_candidates[:top_k]]
