"""
DocuFlow AI — Health Check Endpoints.

Provides:
- /health/live  — Process liveness probe (always 200 if process is up)
- /health/ready — Deep dependency readiness check
- /health/info  — Build info and version metadata
"""

from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.dependencies import DbSession, SettingsDep
from app.infrastructure.logging_config import get_logger
from app.infrastructure.observability import get_metrics

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Returns 200 OK if the process is alive."""
    return {"status": "alive"}


@router.get("/ready", summary="Readiness probe")
async def readiness(settings: SettingsDep, db: DbSession) -> JSONResponse:
    """Checks connectivity to all critical dependencies without exposing internal network/stack details.

    Returns 200 if all dependencies are healthy, 503 if any are degraded.
    """
    checks: dict[str, Any] = {}
    healthy = True

    # --- PostgreSQL ---
    try:
        await db.execute(text("SELECT 1"))
        checks["postgresql"] = {"status": "ok"}
    except Exception as e:
        logger.error("health_check_postgres_failed", error=str(e))
        checks["postgresql"] = {"status": "unhealthy"}
        healthy = False

    # --- Redis ---
    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        checks["redis"] = {"status": "unhealthy"}
        healthy = False

    # --- Qdrant ---
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2) as client:
            url = f"http://{settings.qdrant_host}:{settings.qdrant_port}/healthz"
            resp = await client.get(url)
            if resp.status_code == 200:
                checks["qdrant"] = {"status": "ok"}
            else:
                raise Exception(f"HTTP {resp.status_code}")
    except Exception as e:
        logger.error("health_check_qdrant_failed", error=str(e))
        checks["qdrant"] = {"status": "unhealthy"}
        healthy = False

    # --- MinIO / S3 ---
    try:
        import boto3
        from botocore.config import Config

        s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(connect_timeout=2, read_timeout=2),
        )
        # List buckets is a lightweight connectivity check
        await asyncio.to_thread(s3.list_buckets)
        checks["minio"] = {"status": "ok"}
    except Exception as e:
        logger.error("health_check_minio_failed", error=str(e))
        checks["minio"] = {"status": "unhealthy"}
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "degraded",
            "checks": checks,
        },
    )


@router.get("/metrics", summary="Prometheus Metrics", response_class=Response)
async def metrics() -> Response:
    """Returns application metrics in standard Prometheus exposition format."""
    prometheus_data = get_metrics().generate_prometheus_output()
    return Response(
        content=prometheus_data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/info", summary="Build information")
async def build_info(settings: SettingsDep) -> dict[str, Any]:
    """Returns application version and configuration metadata."""
    return {
        "project": settings.project_name,
        "environment": settings.environment,
        "api_version": "v1",
    }
