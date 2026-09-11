"""
DocuFlow AI — Hybrid Document Chunker.

Combines hierarchical section boundary awareness with sliding-window token overlap,
preserving headings, section paths, and table structures while injecting contextual overlap
between adjacent chunks.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from app.infrastructure.chunking.base import BaseChunker, ChunkData, ChunkingOptions
from app.infrastructure.chunking.hierarchical_chunker import HierarchicalChunker
from app.infrastructure.chunking.token_counter import TokenCounter


class HybridChunker(BaseChunker):
    """Hybrid chunker combining hierarchical structural units with sliding token overlap."""

    def __init__(self) -> None:
        self.hierarchical_chunker = HierarchicalChunker()

    def chunk(
        self,
        markdown: str,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        options: ChunkingOptions | None = None,
        ast_dict: dict[str, Any] | None = None,
    ) -> list[ChunkData]:
        opts = options or ChunkingOptions()
        if not markdown or not markdown.strip():
            return []

        # First pass: generate clean hierarchical structural chunks
        base_chunks = self.hierarchical_chunker.chunk(
            markdown=markdown,
            document_id=document_id,
            version_id=version_id,
            options=opts,
            ast_dict=ast_dict,
        )

        if not base_chunks or opts.overlap_tokens <= 0:
            return base_chunks

        # Second pass: apply semantic overlap between adjacent chunks that share section hierarchy
        hybrid_chunks: list[ChunkData] = []
        for idx, current in enumerate(base_chunks):
            new_text = current.text
            overlap_prefix = ""

            # Inject trailing overlap from previous chunk if within same or parent section
            if idx > 0:
                prev_chunk = base_chunks[idx - 1]
                # If they share at least one top-level heading
                shared_hierarchy = (
                    current.heading_hierarchy
                    and prev_chunk.heading_hierarchy
                    and current.heading_hierarchy[0] == prev_chunk.heading_hierarchy[0]
                )
                if shared_hierarchy:
                    prev_lines = prev_chunk.text.splitlines()
                    # Take last 1-2 non-heading lines for context
                    candidate_lines = [
                        line
                        for line in prev_lines
                        if not line.startswith("#") and not line.startswith("|") and line.strip()
                    ]
                    if candidate_lines:
                        context_snippet = candidate_lines[-1]
                        if TokenCounter.count(context_snippet) <= opts.overlap_tokens:
                            overlap_prefix = f"[... {context_snippet}]\n\n"

            if overlap_prefix:
                new_text = overlap_prefix + new_text

            new_token_count = TokenCounter.count(new_text)
            new_checksum = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

            # Deterministic UUID
            chunk_uuid = uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{version_id}:{idx}:{new_checksum}",
            )

            meta = dict(current.chunk_metadata)
            meta["strategy"] = "hybrid"
            meta["token_count"] = new_token_count
            meta["checksum"] = new_checksum
            meta["has_overlap_context"] = bool(overlap_prefix)

            chunk = ChunkData(
                chunk_id=chunk_uuid,
                document_id=document_id,
                version_id=version_id,
                chunk_index=idx,
                text=new_text,
                token_count=new_token_count,
                heading_hierarchy=current.heading_hierarchy,
                page_numbers=current.page_numbers,
                section_path=current.section_path,
                chunk_metadata=meta,
                checksum=new_checksum,
            )
            hybrid_chunks.append(chunk)

        return hybrid_chunks
