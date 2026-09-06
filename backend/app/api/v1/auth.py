"""
DocuFlow AI — Auth API Stub.

Authentication endpoints are scaffolded here.
Full implementation (JWT login, refresh, register) is Phase 3.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/status", summary="Auth system status")
async def auth_status() -> dict[str, str]:
    """Returns placeholder auth status. Full implementation in Phase 3."""
    return {"status": "auth_module_ready", "note": "Login endpoints coming in Phase 3"}
