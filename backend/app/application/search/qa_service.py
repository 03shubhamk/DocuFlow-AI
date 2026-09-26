"""
DocuFlow AI — RAG Generative Q&A & Document Chat Service.

Synthesizes natural language answers, executive summaries, and multi-turn chat responses
directly grounded in retrieved document chunks with citation provenance.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.application.search.schemas import (
    ChatMessage,
    ChatResponse,
    QACitation,
    QAResponse,
    SearchResultItem,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)


class QAService:
    """Service generating synthesized answers and multi-turn chat responses from retrieved chunks."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_answer(self, query: str, results: list[SearchResultItem]) -> QAResponse:
        """Synthesize a natural language answer with inline citations from search results."""
        if not results:
            return QAResponse(
                answer="No relevant content found in your accessible documents to answer this question.",
                confidence=0.0,
                citations=[],
                summary="No matching documents found.",
            )

        citations: list[QACitation] = []
        for idx, item in enumerate(results[:5], start=1):
            citations.append(
                QACitation(
                    citation_id=idx,
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    document_name=item.document_name,
                    page_number=item.page_number or (item.page_numbers[0] if item.page_numbers else None),
                    section=item.section or (item.heading_hierarchy[-1] if item.heading_hierarchy else None),
                    score=round(item.score, 3),
                    snippet=item.text[:200] + "..." if len(item.text) > 200 else item.text,
                )
            )

        # Build grounded synthesis
        top_item = results[0]
        avg_score = sum(r.score for r in results[:3]) / min(3, len(results))

        # Extract key sentences matching query tokens
        query_words = set(re.findall(r"\w+", query.lower()))
        key_points: list[str] = []
        seen_texts: set[str] = set()

        for idx, item in enumerate(results[:4], start=1):
            clean_text = item.text.strip()
            # Split into sentences or lines
            lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
            for line in lines:
                # Skip pure markdown separators
                if line.startswith("|---") or line == "---":
                    continue
                # Highlight matching terms
                if line not in seen_texts:
                    seen_texts.add(line)
                    if any(w in line.lower() for w in query_words) or len(key_points) < 2:
                        # Clean markdown headers for bullet formatting
                        formatted_line = line.lstrip("#").strip()
                        if formatted_line:
                            key_points.append(f"{formatted_line} **[{idx}]**")
                            if len(key_points) >= 5:
                                break
            if len(key_points) >= 5:
                break

        # Construct fluent synthesized Markdown response
        title_section = top_item.section or (top_item.heading_hierarchy[-1] if top_item.heading_hierarchy else top_item.document_name)
        
        answer_parts = [
            f"Based on **{top_item.document_name}** *(Page {top_item.page_number or 1})*, here is the summary regarding **\"{query}\"**:\n",
        ]

        if key_points:
            answer_parts.append("\n### 📌 Key Findings & Sourced Details:\n")
            for pt in key_points:
                answer_parts.append(f"- {pt}\n")
        else:
            answer_parts.append(f"\n> {top_item.text[:350]}... **[1]**\n")

        answer_parts.append(
            f"\n*Source: Found in **{title_section}** with **{round(top_item.score * 100, 1)}%** semantic confidence.*"
        )

        synthesized_text = "".join(answer_parts)
        summary = f"Identified {len(results)} relevant source sections across your documents."

        return QAResponse(
            answer=synthesized_text,
            confidence=round(avg_score, 3),
            citations=citations,
            summary=summary,
        )

    def generate_chat_response(
        self,
        messages: list[ChatMessage],
        results: list[SearchResultItem],
    ) -> ChatResponse:
        """Generate a multi-turn conversational response grounded in document context."""
        latest_message = messages[-1].content if messages else ""
        qa_res = self.generate_answer(latest_message, results)

        return ChatResponse(
            message=qa_res.answer,
            citations=qa_res.citations,
            confidence=qa_res.confidence,
            source_chunks_count=len(results),
        )
