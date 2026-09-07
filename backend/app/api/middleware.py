"""
DocuFlow AI — FastAPI Request/Response Middleware.

- Assigns X-Correlation-ID to every request and response.
- Binds correlation context vars to structlog.
- Handles global exception mapping (DocuFlowException -> RFC 7807).
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.domain.exceptions import DocuFlowException
from app.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects X-Correlation-ID on every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Bind to structlog context for the duration of the request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Correlation-ID"] = correlation_id

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response


def docuflow_exception_handler(request: Request, exc: DocuFlowException) -> JSONResponse:
    """Map DocuFlowException into RFC 7807 Problem Details JSON responses."""
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")

    logger.warning(
        "application_error",
        error_type=exc.error_type,
        status_code=exc.status_code,
        message=exc.message,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": exc.error_type,
            "title": exc.__class__.__name__.replace("Exception", "").replace("Error", " Error"),
            "status": exc.status_code,
            "detail": exc.message,
            "instance": str(request.url.path),
            "correlation_id": correlation_id,
        },
        headers={"Content-Type": "application/problem+json"},
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions."""
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")

    logger.error(
        "unhandled_exception",
        exc_info=True,
        correlation_id=correlation_id,
    )

    return JSONResponse(
        status_code=500,
        content={
            "type": "https://docuflow.ai/errors/internal-error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "instance": str(request.url.path),
            "correlation_id": correlation_id,
        },
        headers={"Content-Type": "application/problem+json"},
    )
