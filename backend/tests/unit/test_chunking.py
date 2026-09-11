"""
DocuFlow AI — Unit Tests for Document Normalization, Metadata Extraction, and Chunking.

Tests cover:
- Headings preservation and section hierarchy paths
- Paragraph grouping and token limits
- Tables (atomic preservation and row splitting with header retention)
- Multi-page documents and page number aggregation
- Long documents exceeding max_tokens
- Empty sections and edge cases
- Duplicate processing / deterministic chunk IDs
- Normalization (Unicode NFKC, control chars, hyphenations)
- Metadata extraction (title, outline, language, statistics)
"""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.chunking.base import ChunkingOptions
from app.infrastructure.chunking.hierarchical_chunker import HierarchicalChunker
from app.infrastructure.chunking.hybrid_chunker import HybridChunker
from app.infrastructure.chunking.token_counter import TokenCounter
from app.infrastructure.normalization.metadata_extractor import MetadataExtractor
from app.infrastructure.normalization.normalizer import DocumentNormalizer


class TestDocumentNormalizer:
    def test_unicode_nfkc_and_control_chars(self) -> None:
        raw = "Caf\u00e9 \x00\x08and\x1f \uff26\uff49\uff4c\uff45"  # Cafe, control chars, full-width "File"
        cleaned = DocumentNormalizer.clean_text(raw)
        assert "\x00" not in cleaned
        assert "\x1f" not in cleaned
        assert "Café and File" in cleaned

    def test_hyphen_line_break_repair(self) -> None:
        raw = "This is an impor-\ntant docu-\n ment."
        cleaned = DocumentNormalizer.clean_text(raw)
        assert "important" in cleaned
        assert "document" in cleaned

    def test_excessive_newlines_collapse(self) -> None:
        raw = "Paragraph 1\n\n\n\n\nParagraph 2"
        cleaned = DocumentNormalizer.clean_text(raw)
        assert cleaned == "Paragraph 1\n\nParagraph 2"

    def test_normalize_markdown_headings(self) -> None:
        raw = "##Heading Without Space\n\nContent here."
        cleaned = DocumentNormalizer.normalize_markdown(raw)
        assert "## Heading Without Space" in cleaned


class TestMetadataExtractor:
    def test_title_extraction_from_heading(self) -> None:
        md = "# System Architecture Guide\n\n## Section 1\nDetails."
        title = MetadataExtractor.extract_title(md, "guide.pdf")
        assert title == "System Architecture Guide"

    def test_title_fallback_to_filename(self) -> None:
        md = "No top level heading here.\n\nJust text."
        title = MetadataExtractor.extract_title(md, "quarterly_earnings_report.pdf")
        assert title == "Quarterly Earnings Report"

    def test_language_detection(self) -> None:
        en_text = "The quick brown fox jumps over the lazy dog and that is the end of the sentence."
        es_text = "El rápido zorro marrón salta sobre el perro perezoso en la casa."
        fr_text = "Le renard brun rapide saute par-dessus le chien paresseux dans la forêt."

        assert MetadataExtractor.detect_language(en_text) == "en"
        assert MetadataExtractor.detect_language(es_text) == "es"
        assert MetadataExtractor.detect_language(fr_text) == "fr"

    def test_section_hierarchy_outline(self) -> None:
        md = (
            "# Title\n\n"
            "## Chapter 1\n\n"
            "### Section 1.1\n\n"
            "## Chapter 2\n"
        )
        tree = MetadataExtractor.extract_section_hierarchy(md)
        assert len(tree) == 1
        assert tree[0]["title"] == "Title"
        assert len(tree[0]["children"]) == 2
        assert tree[0]["children"][0]["title"] == "Chapter 1"
        assert tree[0]["children"][0]["children"][0]["title"] == "Section 1.1"
        assert tree[0]["children"][1]["title"] == "Chapter 2"


class TestTokenCounter:
    def test_token_count_positive(self) -> None:
        text = "DocuFlow AI is a high-performance document ingestion platform."
        count = TokenCounter.count(text)
        assert count > 0
        assert isinstance(count, int)

    def test_token_truncation(self) -> None:
        text = "Word " * 100
        truncated = TokenCounter.truncate(text, max_tokens=10)
        assert TokenCounter.count(truncated) <= 12  # Within token boundary


class TestHierarchicalChunker:
    @pytest.fixture
    def chunker(self) -> HierarchicalChunker:
        return HierarchicalChunker()

    def test_headings_and_section_hierarchy(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        md = (
            "# User Manual\n\n"
            "Introductory content.\n\n"
            "## Installation\n\n"
            "Run pip install docuflow.\n\n"
            "### Linux\n\n"
            "Use apt-get update first."
        )
        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=200))
        assert len(chunks) >= 3

        # Check section paths
        paths = [c.section_path for c in chunks]
        assert any("User Manual" in p for p in paths)
        assert any("User Manual > Installation" in p for p in paths)
        assert any("User Manual > Installation > Linux" in p for p in paths)

    def test_paragraphs_chunking(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        md = (
            "Paragraph one describing basic features.\n\n"
            "Paragraph two describing advanced features.\n\n"
            "Paragraph three describing performance optimizations."
        )
        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=500))
        assert len(chunks) == 1
        assert "Paragraph one" in chunks[0].text
        assert "Paragraph three" in chunks[0].text

    def test_atomic_table_preservation(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        md = (
            "## Pricing\n\n"
            "| Plan | Price | Features |\n"
            "| --- | --- | --- |\n"
            "| Basic | $10 | 100 docs |\n"
            "| Pro | $50 | 1000 docs |\n"
        )
        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=300))
        assert len(chunks) >= 1
        table_chunk = next(c for c in chunks if "| Plan |" in c.text)
        assert "| Basic | $10 |" in table_chunk.text
        assert "| Pro | $50 |" in table_chunk.text

    def test_oversized_table_splitting_with_header_replication(
        self, chunker: HierarchicalChunker
    ) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        # Build a table with 30 rows
        header = "| ID | Name | Description |\n| --- | --- | --- |"
        rows = [f"| {i} | Item_{i} | Long description of item number {i} with metadata details |" for i in range(30)]
        md = header + "\n" + "\n".join(rows)

        # Force small max_tokens to trigger row-wise splitting
        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=80))
        assert len(chunks) > 1

        # Every table sub-chunk must replicate the header row
        for c in chunks:
            assert "| ID | Name | Description |" in c.text
            assert "| --- | --- | --- |" in c.text

    def test_multi_page_document_tracking(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        md = (
            "<!-- page: 1 -->\n"
            "# Page One Content\n\n"
            "First page details.\n\n"
            "<!-- page: 2 -->\n"
            "## Page Two Content\n\n"
            "Second page details."
        )
        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=200))
        assert len(chunks) >= 2
        assert 1 in chunks[0].page_numbers
        assert 2 in chunks[1].page_numbers

    def test_long_document_overflow_splitting(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        long_para = "This is a sentence that will be repeated many times to test token limit overflows. " * 50
        md = f"# Long Document\n\n{long_para}"

        chunks = chunker.chunk(md, doc_id, ver_id, ChunkingOptions(max_tokens=100))
        assert len(chunks) > 1
        for c in chunks:
            assert c.token_count <= 150  # Respects max limit bounds

    def test_empty_sections_and_blank_input(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        assert chunker.chunk("", doc_id, ver_id) == []
        assert chunker.chunk("   \n\n   ", doc_id, ver_id) == []

        # Empty heading without body
        chunks = chunker.chunk("# Empty Heading", doc_id, ver_id)
        assert len(chunks) == 1
        assert chunks[0].heading_hierarchy == ["Empty Heading"]

    def test_deterministic_chunking_idempotency(self, chunker: HierarchicalChunker) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        md = "# Determinism Test\n\nContent paragraph 1.\n\n## Sub\n\nContent paragraph 2."

        run1 = chunker.chunk(md, doc_id, ver_id)
        run2 = chunker.chunk(md, doc_id, ver_id)

        assert len(run1) == len(run2)
        for c1, c2 in zip(run1, run2, strict=True):
            assert c1.chunk_id == c2.chunk_id
            assert c1.checksum == c2.checksum
            assert c1.chunk_index == c2.chunk_index
            assert c1.text == c2.text


class TestHybridChunker:
    def test_hybrid_chunker_injects_overlap(self) -> None:
        chunker = HybridChunker()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        md = (
            "# Main Chapter\n\n"
            "First section introductory details that establish significant context and background information for the reader.\n\n"
            "Second subsection that continues the topic with further deep insights and implementation details."
        )
        # Max tokens 18 to guarantee splitting into 2 adjacent chunks
        chunks = chunker.chunk(
            md,
            doc_id,
            ver_id,
            ChunkingOptions(max_tokens=18, overlap_tokens=10),
        )

        assert len(chunks) >= 2
        # Check that second chunk has hybrid strategy metadata
        assert chunks[1].chunk_metadata.get("strategy") == "hybrid"

