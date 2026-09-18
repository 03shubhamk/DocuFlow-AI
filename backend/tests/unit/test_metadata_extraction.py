"""
DocuFlow AI — Unit Tests for Document Normalization & Metadata Extraction.

Tests AST normalization, hierarchy preservation, table/figure preservation,
and metadata extraction.
"""

from __future__ import annotations

import hashlib

from app.infrastructure.normalization.metadata_extractor import (
    ExtractedMetadata,
    MetadataExtractor,
    SectionNode,
)
from app.infrastructure.normalization.normalizer import DocumentNormalizer


class TestMetadataExtractionAndNormalization:
    def test_extracted_metadata_entity_fields(self):
        meta = ExtractedMetadata(
            title="Q3 Financial Intelligence Report",
            filename="q3_report.pdf",
            file_type="application/pdf",
            page_count=12,
            language="en",
            section_hierarchy=[SectionNode(title="Executive Summary", level=1, page=1).to_dict()],
            table_count=2,
            figure_count=1,
            word_count=500,
            character_count=3200,
            checksum=hashlib.sha256(b"content").hexdigest(),
            processing_version="1.0.0",
            parser_version="docling-2.0.0",
        )

        assert meta.title == "Q3 Financial Intelligence Report"
        assert meta.page_count == 12
        assert meta.language == "en"
        assert len(meta.section_hierarchy) == 1
        assert meta.table_count == 2
        assert meta.checksum is not None

    def test_document_normalizer_and_extractor(self):
        raw_md = "# Executive Summary\n\nDocuFlow AI extracts deep document semantics."
        raw_text = "Executive Summary\n\nDocuFlow AI extracts deep document semantics."

        cleaned_md = DocumentNormalizer.normalize_markdown(raw_md)
        cleaned_text = DocumentNormalizer.clean_text(raw_text)
        assert cleaned_md is not None
        assert cleaned_text is not None

        extracted = MetadataExtractor.extract(
            markdown=cleaned_md,
            plain_text=cleaned_text,
            filename="exec_summary.pdf",
            file_type="application/pdf",
            checksum="abc123sha",
            page_count=2,
            table_count=1,
        )
        assert extracted.filename == "exec_summary.pdf"
        assert extracted.page_count == 2
        assert extracted.checksum == "abc123sha"
        assert extracted.title == "Executive Summary"


