"""
DocuFlow AI — In-Memory Mock Document Processor.

Used for fast, deterministic unit and integration tests without downloading
multi-gigabyte neural network model weights.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.infrastructure.processors.base import (
    DocumentProcessor,
    ProcessedDocument,
    ProcessingOptions,
)


class MockDocumentProcessor(DocumentProcessor):
    """Fast mock document processor returning valid Docling-like AST structures."""

    async def process(
        self,
        source_path: Path,
        mime_type: str,
        options: ProcessingOptions | None = None,
    ) -> ProcessedDocument:
        start_time = time.perf_counter()

        content_bytes = source_path.read_bytes()
        file_ext = source_path.suffix.lower()

        # Generate sensible mock text and markdown based on input format
        if file_ext in {".txt", ".md", ".html"}:
            try:
                raw_text = content_bytes.decode("utf-8", errors="replace")
            except Exception:
                raw_text = str(content_bytes)
            markdown = raw_text if file_ext != ".html" else f"# Extracted HTML\n\n{raw_text}"
            plain_text = raw_text
        elif file_ext == ".pdf":
            try:
                decoded = content_bytes.decode("utf-8", errors="ignore")
                lines = [
                    line.strip()
                    for line in decoded.splitlines()
                    if line.strip()
                    and not line.startswith("%PDF")
                    and "obj" not in line
                    and "endobj" not in line
                    and "xref" not in line
                    and "trailer" not in line
                    and "startxref" not in line
                    and "%%EOF" not in line
                ]
                custom_text = "\n\n".join(lines)
            except Exception:
                custom_text = ""

            if custom_text and len(custom_text) > 5:
                markdown = f"# Processed Document\n\n{custom_text}"
                plain_text = custom_text
            else:
                raw_text = "Extracted PDF Document Content\n\n## Section 1: Executive Summary\n\nThis is a processed PDF document."
                markdown = "# Processed Document\n\n## Section 1: Executive Summary\n\nThis is a processed PDF document.\n\n| Column 1 | Column 2 |\n|---|---|\n| Data A | Data B |"
                plain_text = "Processed Document\nSection 1: Executive Summary\nThis is a processed PDF document."
        elif file_ext in {".docx", ".pptx", ".xlsx"}:
            markdown = f"# Office Document ({file_ext})\n\nExtracted content from {source_path.name}."
            plain_text = f"Office Document ({file_ext})\nExtracted content from {source_path.name}."
        else:
            # Images
            markdown = f"# Scanned Image Asset\n\nOCR Extracted text from {source_path.name}."
            plain_text = f"Scanned Image Asset\nOCR Extracted text from {source_path.name}."

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Simulated DoclingDocument JSON AST
        json_dict: dict[str, Any] = {
            "schema_name": "DoclingDocument",
            "version": "1.0.0",
            "name": source_path.stem,
            "origin": {
                "filename": source_path.name,
                "mime_type": mime_type,
                "binary_hash": len(content_bytes),
            },
            "body": {
                "children": [
                    {
                        "label": "section_header",
                        "text": "Processed Document",
                        "prov": [{"page_no": 1, "bbox": [50.0, 700.0, 300.0, 750.0]}],
                    },
                    {
                        "label": "paragraph",
                        "text": plain_text,
                        "prov": [{"page_no": 1, "bbox": [50.0, 500.0, 500.0, 680.0]}],
                    },
                    {
                        "label": "table",
                        "data": {"num_rows": 2, "num_cols": 2},
                        "prov": [{"page_no": 1, "bbox": [50.0, 300.0, 450.0, 480.0]}],
                    },
                ]
            },
        }

        # Mock figure PNG asset
        figures: dict[str, bytes] = {}
        if options and options.extract_figures:
            # 1x1 transparent PNG
            figures["figure_001.png"] = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
                b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        page_count = 1
        if file_ext == ".pdf":
            import re
            pdf_str = content_bytes.decode("latin1", errors="ignore")
            pdf_pages = len(re.findall(r"/Type\s*/Page\b", pdf_str))
            if pdf_pages > 0:
                page_count = pdf_pages
            else:
                page_markers = re.findall(r"\bPage\s+\d+\b", plain_text)
                if page_markers:
                    page_count = len(set(page_markers))

        metadata: dict[str, Any] = {
            "title": source_path.stem.replace("_", " ").title(),
            "page_count": page_count,
            "table_count": 1,
            "figure_count": len(figures),
            "word_count": len(plain_text.split()),
            "character_count": len(plain_text),
            "duration_ms": round(duration_ms, 2),
            "ocr_applied": bool(options and options.do_ocr),
            "ocr_provider": options.ocr_provider if options else "none",
        }

        return ProcessedDocument(
            markdown=markdown,
            plain_text=plain_text,
            json_dict=json_dict,
            metadata=metadata,
            figures=figures,
            duration_ms=round(duration_ms, 2),
        )
