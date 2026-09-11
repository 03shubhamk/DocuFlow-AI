"""
DocuFlow AI — Chunking Core Abstractions and Data Models.

Defines ChunkData dataclass and BaseChunker interface for all chunking strategies.
"""

from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ChunkData:
    """Represents a discrete, structured chunk of a document version."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    heading_hierarchy: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=lambda: [1])
    section_path: str = ""
    chunk_metadata: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = hashlib.sha256(self.text.encode("utf-8")).hexdigest()

        if not self.section_path and self.heading_hierarchy:
            self.section_path = " > ".join(self.heading_hierarchy)

        # Ensure metadata contains standard fields
        self.chunk_metadata.setdefault("checksum", self.checksum)
        self.chunk_metadata.setdefault("section_path", self.section_path)
        self.chunk_metadata.setdefault("heading_hierarchy", self.heading_hierarchy)
        self.chunk_metadata.setdefault("page_numbers", self.page_numbers)
        self.chunk_metadata.setdefault("token_count", self.token_count)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["chunk_id"] = str(self.chunk_id)
        d["document_id"] = str(self.document_id)
        d["version_id"] = str(self.version_id)
        return d


@dataclass
class ChunkingOptions:
    """Configuration options for chunking engine execution."""

    max_tokens: int = 512
    overlap_tokens: int = 64
    min_tokens: int = 30
    preserve_tables: bool = True
    include_hierarchy_in_text: bool = False
    source_filename: str = ""


class BaseChunker(ABC):
    """Abstract base class for document chunkers."""

    @abstractmethod
    def chunk(
        self,
        markdown: str,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        options: ChunkingOptions | None = None,
        ast_dict: dict[str, Any] | None = None,
    ) -> list[ChunkData]:
        """Split document into a deterministic list of ChunkData items."""
        pass
