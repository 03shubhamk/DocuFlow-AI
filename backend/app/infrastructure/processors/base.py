"""
DocuFlow AI — Document Processor Abstract Base Class and Domain DTOs.

Defines the contract for all document parsing engines (Docling, Mock).
Decouples application workflow from specific parsing libraries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProcessingOptions:
    """Configurable options for document parsing execution."""

    do_ocr: bool = True
    ocr_provider: str = "easyocr"
    ocr_languages: list[str] = field(default_factory=lambda: ["en"])
    do_table_structure: bool = True
    extract_figures: bool = True
    generate_page_images: bool = False


@dataclass
class ProcessedDocument:
    """Unified structured output produced by document processing."""

    markdown: str
    plain_text: str
    json_dict: dict[str, Any]
    metadata: dict[str, Any]
    figures: dict[str, bytes] = field(default_factory=dict)
    duration_ms: float = 0.0
    docling_document: Any | None = None

    @property
    def page_count(self) -> int:
        return int(self.metadata.get("page_count", 1))

    @property
    def table_count(self) -> int:
        return int(self.metadata.get("table_count", 0))

    @property
    def figure_count(self) -> int:
        return int(self.metadata.get("figure_count", len(self.figures)))


class DocumentProcessor(ABC):
    """Abstract interface for document intelligence processing engines."""

    @abstractmethod
    async def process(
        self,
        source_path: Path,
        mime_type: str,
        options: ProcessingOptions | None = None,
    ) -> ProcessedDocument:
        """Process a document file into unified structured representations.

        Args:
            source_path: Local filesystem path to the input document.
            mime_type: Declared or resolved MIME type of the document.
            options: Optional parsing and OCR configuration.

        Returns:
            ProcessedDocument containing JSON AST, Markdown, text, and extracted assets.
        """
