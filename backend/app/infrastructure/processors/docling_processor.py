"""
DocuFlow AI — IBM Docling Document Processor Implementation.

Uses IBM Docling 2.x DocumentConverter to convert multi-format documents
(PDF, DOCX, PPTX, XLSX, HTML, Markdown, TXT, Images) into unified DoclingDocument ASTs.
Preserves structural hierarchy, headings, tables, pictures, reading order, and layout provenance.
"""

from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings
from app.infrastructure.processors.base import (
    DocumentProcessor,
    ProcessedDocument,
    ProcessingOptions,
)

logger = structlog.get_logger(__name__)


class DoclingDocumentProcessor(DocumentProcessor):
    """Production document processor using IBM Docling 2.x unified document representations."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._converter: Any = None
        self._init_error: Exception | None = None

    def _build_converter(self, options: ProcessingOptions) -> Any:
        """Construct a configured Docling DocumentConverter instance."""
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = options.do_ocr
            pipeline_options.do_table_structure = options.do_table_structure
            pipeline_options.generate_picture_images = options.extract_figures

            # Configure OCR backend
            if options.do_ocr and options.ocr_provider != "none":
                ocr_prov = options.ocr_provider.lower()
                try:
                    if ocr_prov == "easyocr":
                        from docling.datamodel.pipeline_options import EasyOcrOptions

                        pipeline_options.ocr_options = EasyOcrOptions(lang=options.ocr_languages)
                    elif ocr_prov in {"tesseract", "tesseract_cli"}:
                        from docling.datamodel.pipeline_options import TesseractOcrOptions

                        pipeline_options.ocr_options = TesseractOcrOptions(lang=options.ocr_languages)
                    elif ocr_prov == "rapidocr":
                        from docling.datamodel.pipeline_options import RapidOcrOptions

                        pipeline_options.ocr_options = RapidOcrOptions()
                except (ImportError, Exception) as ocr_err:
                    logger.warning("ocr_provider_init_failed", provider=ocr_prov, error=str(ocr_err))

            format_options: dict[Any, Any] = {
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                InputFormat.IMAGE: PdfFormatOption(pipeline_options=pipeline_options),
            }

            return DocumentConverter(format_options=format_options)
        except ImportError as e:
            logger.error("docling_import_error", error=str(e))
            self._init_error = e
            return None

    async def process(
        self,
        source_path: Path,
        mime_type: str,
        options: ProcessingOptions | None = None,
    ) -> ProcessedDocument:
        """Convert a document file into unified JSON AST, Markdown, text, and extracted assets."""
        opts = options or ProcessingOptions(
            do_ocr=self.settings.ocr_enabled,
            ocr_provider=self.settings.ocr_provider,
            ocr_languages=self.settings.ocr_languages,
        )

        converter = self._build_converter(opts)
        if converter is None:
            # Fallback to mock/lightweight processor if docling is not installed in environment
            from app.infrastructure.processors.mock_processor import MockDocumentProcessor

            logger.warning("using_mock_fallback_processor", reason=str(self._init_error))
            mock = MockDocumentProcessor()
            return await mock.process(source_path, mime_type, opts)

        start_time = time.perf_counter()

        def _sync_convert() -> Any:
            return converter.convert(source_path)

        try:
            conv_result = await asyncio.to_thread(_sync_convert)
            docling_doc = conv_result.document
        except Exception as e:
            logger.error("docling_conversion_failed", path=str(source_path), error=str(e))
            raise RuntimeError(f"Docling processing failed for '{source_path.name}': {e}") from e

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Export structured representations
        json_dict = docling_doc.export_to_dict()
        markdown = docling_doc.export_to_markdown()

        # Text extraction
        if hasattr(docling_doc, "export_to_text"):
            plain_text = docling_doc.export_to_text()
        else:
            # Clean markdown to plain text fallback
            import re

            plain_text = re.sub(r"[#*_`\[\]\(\)]", "", markdown)

        # Extract figures / pictures if available
        figures: dict[str, bytes] = {}
        if opts.extract_figures and hasattr(docling_doc, "pictures"):
            for idx, pic in enumerate(docling_doc.pictures):
                if hasattr(pic, "image") and pic.image is not None:
                    try:
                        buf = io.BytesIO()
                        # pic.image is a PIL.Image
                        pic.image.save(buf, format="PNG")
                        fig_name = f"picture_{idx + 1:03d}.png"
                        figures[fig_name] = buf.getvalue()
                    except Exception as img_err:
                        logger.warning("picture_extraction_warning", index=idx, error=str(img_err))

        # Metadata extraction
        page_count = len(getattr(docling_doc, "pages", {})) or 1
        table_count = len(getattr(docling_doc, "tables", []))
        figure_count = len(figures) or len(getattr(docling_doc, "pictures", []))
        word_count = len(plain_text.split())

        metadata: dict[str, Any] = {
            "title": getattr(docling_doc, "name", source_path.stem),
            "page_count": page_count,
            "table_count": table_count,
            "figure_count": figure_count,
            "word_count": word_count,
            "character_count": len(plain_text),
            "duration_ms": round(duration_ms, 2),
            "ocr_applied": opts.do_ocr,
            "ocr_provider": opts.ocr_provider,
            "docling_version": "2.x",
        }

        return ProcessedDocument(
            markdown=markdown,
            plain_text=plain_text,
            json_dict=json_dict,
            metadata=metadata,
            figures=figures,
            duration_ms=round(duration_ms, 2),
            docling_document=docling_doc,
        )
