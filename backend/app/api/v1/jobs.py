"""Jobs API stub — Phase 3 implementation."""
from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", summary="Get job status (stub)")
async def get_job(job_id: str) -> dict:
    return {"job_id": job_id, "note": "Full implementation in Phase 3"}
