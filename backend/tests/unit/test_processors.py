"""
DocuFlow AI — Unit Tests for Document Processors and OCR Configuration.

Tests MockDocumentProcessor, DoclingDocumentProcessor construction, format handling,
and OCR pipeline options.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.infrastructure.processors.base import ProcessingOptions
from app.infrastructure.processors.docling_processor import DoclingDocumentProcessor
from app.infrastructure.processors.mock_processor import MockDocumentProcessor


@pytest.mark.asyncio
async def test_mock_processor_pdf() -> None:
    processor = MockDocumentProcessor()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\nTest PDF content")
        tmp_path = Path(tmp.name)

    try:
        processed = await processor.process(
            source_path=tmp_path,
            mime_type="application/pdf",
            options=ProcessingOptions(do_ocr=True, ocr_provider="easyocr", extract_figures=True),
        )

        assert "Processed Document" in processed.markdown
        assert processed.page_count >= 1
        assert "schema_name" in processed.json_dict
        assert processed.json_dict["schema_name"] == "DoclingDocument"
        assert len(processed.figures) >= 1
        assert processed.duration_ms > 0
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_mock_processor_docx() -> None:
    processor = MockDocumentProcessor()
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(b"PK\x03\x04Mock Docx")
        tmp_path = Path(tmp.name)

    try:
        processed = await processor.process(
            source_path=tmp_path,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert "Office Document (.docx)" in processed.markdown
        assert processed.table_count >= 1
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_mock_processor_image_ocr() -> None:
    processor = MockDocumentProcessor()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(b"\x89PNG\r\n\x1a\nMock PNG")
        tmp_path = Path(tmp.name)

    try:
        processed = await processor.process(
            source_path=tmp_path,
            mime_type="image/png",
            options=ProcessingOptions(do_ocr=True, ocr_provider="easyocr"),
        )
        assert "Scanned Image Asset" in processed.markdown
        assert processed.metadata["ocr_applied"] is True
        assert processed.metadata["ocr_provider"] == "easyocr"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_docling_processor_converter_configuration() -> None:
    import sys
    from unittest.mock import MagicMock

    mock_docling = MagicMock()
    mock_docling_converter = MagicMock()
    mock_docling_pipeline = MagicMock()
    mock_docling_base = MagicMock()

    mock_converter_cls = MagicMock()
    mock_docling_converter.DocumentConverter = mock_converter_cls
    mock_docling_converter.PdfFormatOption = MagicMock()
    mock_docling_base.InputFormat = MagicMock()
    mock_docling_pipeline.PdfPipelineOptions = MagicMock()
    mock_docling_pipeline.EasyOcrOptions = MagicMock()
    mock_docling_pipeline.TesseractOcrOptions = MagicMock()

    modules_to_patch = {
        "docling": mock_docling,
        "docling.document_converter": mock_docling_converter,
        "docling.datamodel": MagicMock(),
        "docling.datamodel.base_models": mock_docling_base,
        "docling.datamodel.pipeline_options": mock_docling_pipeline,
    }

    from unittest.mock import patch

    with patch.dict(sys.modules, modules_to_patch):
        processor = DoclingDocumentProcessor()

        # Test EasyOCR provider options
        opts_easyocr = ProcessingOptions(do_ocr=True, ocr_provider="easyocr", ocr_languages=["en", "es"])
        conv_easy = processor._build_converter(opts_easyocr)
        assert conv_easy is not None
        assert mock_converter_cls.called

        # Test Tesseract provider options
        opts_tesseract = ProcessingOptions(do_ocr=True, ocr_provider="tesseract", ocr_languages=["en"])
        conv_tess = processor._build_converter(opts_tesseract)
        assert conv_tess is not None

        # Test disabled OCR
        opts_none = ProcessingOptions(do_ocr=False, ocr_provider="none")
        conv_none = processor._build_converter(opts_none)
        assert conv_none is not None


