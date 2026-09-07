"""Documents API stub — Phase 3 implementation."""

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", summary="List documents (stub)")
async def list_documents() -> dict:
    return {"items": [], "pagination": {"total_items": 0}, "note": "Full implementation in Phase 3"}
