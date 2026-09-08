"""
DocuFlow AI — Processors Infrastructure Package.

Provides document processor abstractions, implementations, and singleton factory.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.processors.base import (
    DocumentProcessor,
    ProcessedDocument,
    ProcessingOptions,
)
from app.infrastructure.processors.docling_processor import DoclingDocumentProcessor
from app.infrastructure.processors.mock_processor import MockDocumentProcessor

__all__ = [
    "DocumentProcessor",
    "DoclingDocumentProcessor",
    "MockDocumentProcessor",
    "ProcessedDocument",
    "ProcessingOptions",
    "get_document_processor",
]


@lru_cache(maxsize=1)
def get_document_processor() -> DocumentProcessor:
    """Factory creating and caching the configured DocumentProcessor instance."""
    settings = get_settings()

    if settings.environment == "testing":
        return MockDocumentProcessor()

    return DoclingDocumentProcessor()
