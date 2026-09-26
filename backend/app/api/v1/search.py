"""
DocuFlow AI — Document Search API Router.

Provides authenticated endpoints for multi-tenant semantic vector search and hybrid retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DbSession
from app.application.search.schemas import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
)
from app.application.search.service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search document chunks using semantic or hybrid retrieval",
    description=(
        "Executes multi-tenant semantic vector search over indexed document chunks. "
        "Supports query embedding generation, score thresholding, metadata filtering, "
        "scoped document filters, and optional hybrid lexical fusion."
    ),
)
async def search_documents(
    body: SearchRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SearchResponse:
    """Execute document search and return ranked results with chunk metadata and AI synthesized answer."""
    service = SearchService(session=db)
    return await service.search(
        request=body,
        current_user=current_user.to_entity(),
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Conversational Q&A chat over document library",
    description="Multi-turn RAG chat assistant answering user questions with grounded document citations.",
)
async def chat_documents(
    body: ChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ChatResponse:
    """Execute conversational chat grounded in document knowledge."""
    service = SearchService(session=db)
    return await service.chat(
        request=body,
        current_user=current_user.to_entity(),
    )

