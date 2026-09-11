"""
DocuFlow AI — Intelligent Chunking Module.
"""

from app.infrastructure.chunking.base import BaseChunker, ChunkData, ChunkingOptions
from app.infrastructure.chunking.hierarchical_chunker import HierarchicalChunker
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.token_counter import TokenCounter


def get_chunker(strategy: str = "hierarchical") -> BaseChunker:
    """Factory creating configured chunker instance based on strategy."""
    strat = strategy.lower().strip()
    if strat in {"hybrid", "sliding_window"}:
        return HybridChunker()
    return HierarchicalChunker()


__all__ = [
    "BaseChunker",
    "ChunkData",
    "ChunkingOptions",
    "HierarchicalChunker",
    "HybridChunker",
    "TokenCounter",
    "get_chunker",
]
