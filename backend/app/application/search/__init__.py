"""
DocuFlow AI — Search Application Package.
"""

from __future__ import annotations

from app.application.search.schemas import (
    DocumentStructureResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.application.search.service import SearchService
from app.application.search.strategies import (
    DenseSearchStrategy,
    HybridSearchStrategy,
    SearchStrategy,
)

__all__ = [
    "DenseSearchStrategy",
    "DocumentStructureResponse",
    "HybridSearchStrategy",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SearchService",
    "SearchStrategy",
]
