"""
DocuFlow AI — Document Search API Router.

Provides authenticated endpoints for multi-tenant semantic vector search and hybrid retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DbSession
from app.application.search.schemas import SearchRequest, SearchResponse
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
    """Execute document search and return ranked results with chunk metadata."""
    service = SearchService(session=db)
    return await service.search(
        request=body,
        current_user=current_user.to_entity(),
    )
