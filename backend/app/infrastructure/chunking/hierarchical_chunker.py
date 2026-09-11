"""
DocuFlow AI — Hierarchical / Structure-Aware Document Chunker.

Preserves heading hierarchies, section paths, table integrity, and page provenance.
Splits large tables row-wise with header replication, and segments long sections
without breaking paragraph boundaries.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from app.infrastructure.chunking.base import BaseChunker, ChunkData, ChunkingOptions
from app.infrastructure.chunking.token_counter import TokenCounter


class HierarchicalChunker(BaseChunker):
    """Structure-aware chunker respecting section trees, headings, tables, and pages."""

    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
    _TABLE_ROW_RE = re.compile(r"^\|.+\|$")
    _PAGE_BREAK_RE = re.compile(r"<!--\s*page\s*:\s*(\d+)\s*-->", re.IGNORECASE)

    def _split_oversized_table(
        self,
        table_lines: list[str],
        max_tokens: int,
    ) -> list[str]:
        """Split a large table into multiple smaller tables, replicating header rows."""
        if len(table_lines) < 3:
            return ["\n".join(table_lines)]

        header_lines = table_lines[:2]  # Column headers + delimiter row
        header_text = "\n".join(header_lines)
        header_tokens = TokenCounter.count(header_text)
        available_tokens = max(50, max_tokens - header_tokens - 10)

        data_rows = table_lines[2:]
        chunks: list[str] = []
        current_rows: list[str] = []
        current_tokens = 0

        for row in data_rows:
            row_tokens = TokenCounter.count(row)
            if current_tokens + row_tokens > available_tokens and current_rows:
                chunk_str = header_text + "\n" + "\n".join(current_rows)
                chunks.append(chunk_str)
                current_rows = [row]
                current_tokens = row_tokens
            else:
                current_rows.append(row)
                current_tokens += row_tokens

        if current_rows:
            chunk_str = header_text + "\n" + "\n".join(current_rows)
            chunks.append(chunk_str)

        return chunks

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

        lines = markdown.splitlines()
        chunks: list[ChunkData] = []
        chunk_index = 0

        # State tracking
        heading_stack: list[tuple[int, str]] = []  # [(level, title)]
        current_page = 1
        current_pages: set[int] = {1}
        current_text_blocks: list[str] = []
        current_tokens = 0

        def emit_current_chunk() -> None:
            nonlocal chunk_index, current_text_blocks, current_tokens, current_pages
            if not current_text_blocks:
                return

            chunk_text = "\n\n".join(current_text_blocks).strip()
            if not chunk_text:
                current_text_blocks = []
                current_tokens = 0
                return

            headings = [h[1] for h in heading_stack]
            sec_path = " > ".join(headings)
            pages = sorted(list(current_pages)) or [current_page]
            t_count = TokenCounter.count(chunk_text)
            c_sum = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()

            # Deterministic UUID generation
            chunk_uuid = uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{version_id}:{chunk_index}:{c_sum}",
            )

            meta: dict[str, Any] = {
                "chunk_index": chunk_index,
                "section_path": sec_path,
                "heading_hierarchy": headings,
                "page_numbers": pages,
                "token_count": t_count,
                "checksum": c_sum,
                "strategy": "hierarchical",
            }
            if opts.source_filename:
                meta["source_document"] = opts.source_filename

            chunk = ChunkData(
                chunk_id=chunk_uuid,
                document_id=document_id,
                version_id=version_id,
                chunk_index=chunk_index,
                text=chunk_text,
                token_count=t_count,
                heading_hierarchy=headings,
                page_numbers=pages,
                section_path=sec_path,
                chunk_metadata=meta,
                checksum=c_sum,
            )
            chunks.append(chunk)
            chunk_index += 1

            # Reset current buffer
            current_text_blocks = []
            current_tokens = 0
            current_pages = {current_page}

        # Step through lines assembling structural units (headings, paragraphs, tables)
        i = 0
        while i < len(lines):
            line = lines[i]

            # 1. Page marker check
            page_match = self._PAGE_BREAK_RE.search(line)
            if page_match:
                current_page = int(page_match.group(1))
                current_pages.add(current_page)
                i += 1
                continue

            # 2. Heading check
            heading_match = self._HEADING_RE.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Emit previous accumulated text if any
                if current_text_blocks:
                    emit_current_chunk()

                # Update heading stack
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))

                # Include heading in next chunk
                current_text_blocks.append(line)
                current_tokens += TokenCounter.count(line)
                current_pages.add(current_page)
                i += 1
                continue

            # 3. Table check
            if self._TABLE_ROW_RE.match(line):
                table_lines = []
                while i < len(lines) and (self._TABLE_ROW_RE.match(lines[i]) or not lines[i].strip()):
                    if lines[i].strip():
                        table_lines.append(lines[i].strip())
                    i += 1

                if table_lines:
                    table_text = "\n".join(table_lines)
                    table_tokens = TokenCounter.count(table_text)

                    if table_tokens > opts.max_tokens and opts.preserve_tables:
                        # Split large table row-wise
                        sub_tables = self._split_oversized_table(table_lines, opts.max_tokens)
                        for st in sub_tables:
                            if current_text_blocks:
                                emit_current_chunk()
                            current_text_blocks.append(st)
                            current_tokens += TokenCounter.count(st)
                            current_pages.add(current_page)
                            emit_current_chunk()
                    else:
                        if current_tokens + table_tokens > opts.max_tokens and current_text_blocks:
                            emit_current_chunk()
                        current_text_blocks.append(table_text)
                        current_tokens += table_tokens
                        current_pages.add(current_page)
                continue

            # 4. Standard paragraph block
            if line.strip():
                para_lines = []
                while i < len(lines) and lines[i].strip() and not self._HEADING_RE.match(lines[i]) and not self._TABLE_ROW_RE.match(lines[i]) and not self._PAGE_BREAK_RE.search(lines[i]):
                    para_lines.append(lines[i])
                    i += 1

                para_text = "\n".join(para_lines).strip()
                para_tokens = TokenCounter.count(para_text)

                # Check if paragraph itself exceeds max_tokens
                if para_tokens > opts.max_tokens:
                    if current_text_blocks:
                        emit_current_chunk()
                    # Subdivide long paragraph
                    sub_paras = TokenCounter.split_by_tokens(para_text, opts.max_tokens, opts.overlap_tokens)
                    for sp in sub_paras:
                        current_text_blocks.append(sp)
                        current_tokens += TokenCounter.count(sp)
                        current_pages.add(current_page)
                        emit_current_chunk()
                else:
                    if current_tokens + para_tokens > opts.max_tokens and current_text_blocks:
                        emit_current_chunk()
                    current_text_blocks.append(para_text)
                    current_tokens += para_tokens
                    current_pages.add(current_page)
                continue

            i += 1

        # Emit any remaining content
        if current_text_blocks:
            emit_current_chunk()

        return chunks
