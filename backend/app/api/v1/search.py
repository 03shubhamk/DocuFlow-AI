"""Search API stub — Phase 5 implementation."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


@router.post("/", summary="Semantic search (stub)")
async def search_documents(body: SearchRequest) -> dict:
    return {"query": body.query, "results": [], "note": "Full implementation in Phase 5"}
