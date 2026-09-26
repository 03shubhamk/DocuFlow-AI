"""
DocuFlow AI — Search Application DTOs and Response Schemas.

Defines validated Pydantic schemas for semantic vector search, hybrid retrieval,
ranked result serialization, and document structure inspection.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Payload for executing document search."""

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum number of ranked results to return")
    document_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Optional list of document IDs to restrict search scope",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Optional document page filter or pagination page number",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary payload metadata filters (e.g. {'mime_type': '.pdf'})",
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (0.0 to 1.0)",
    )
    strategy: str | None = Field(
        default=None,
        description="Search execution strategy: 'dense' (default) or 'hybrid'",
    )
    page_size: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Optional page size if paginating search results",
    )


class SearchResultItem(BaseModel):
    """Ranked search result item representing an indexed document chunk."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    score: float
    text: str
    page_number: int | None = None
    page_numbers: list[int] = Field(default_factory=list)
    section: str | None = None
    heading_hierarchy: list[str] = Field(default_factory=list)
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class QACitation(BaseModel):
    """Citation reference linked to source document chunk."""

    citation_id: int
    chunk_id: uuid.UUID | None = None
    document_id: uuid.UUID
    document_name: str
    page_number: int | None = None
    section: str | None = None
    score: float
    snippet: str


class QAResponse(BaseModel):
    """Synthesized natural language answer with source citations."""

    answer: str
    confidence: float
    citations: list[QACitation] = Field(default_factory=list)
    summary: str | None = None


class ChatMessage(BaseModel):
    """A single chat message in conversational Q&A."""

    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """Payload for conversational Q&A over document library."""

    messages: list[ChatMessage]
    document_ids: list[uuid.UUID] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    """Conversational chat response with grounded sources."""

    message: str
    citations: list[QACitation] = Field(default_factory=list)
    confidence: float
    source_chunks_count: int


class SearchResponse(BaseModel):
    """Structured response container for search results."""

    results: list[SearchResultItem]
    total: int
    query: str
    top_k: int
    page: int | None = None
    page_size: int | None = None
    strategy_used: str
    duration_ms: float
    ai_answer: str | None = None
    citations: list[QACitation] = Field(default_factory=list)


class DocumentStructureResponse(BaseModel):
    """Hierarchical structural outline and metadata overview of a document."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    version_id: uuid.UUID
    title: str
    original_filename: str
    file_type: str
    page_count: int
    chunk_count: int
    language: str
    table_count: int
    figure_count: int
    section_hierarchy: list[dict[str, Any]] = Field(default_factory=list)

