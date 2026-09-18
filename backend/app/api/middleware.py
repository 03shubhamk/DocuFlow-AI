"""
DocuFlow AI — FastAPI Request/Response Middleware & Observability.

- Assigns X-Correlation-ID & request_id to every request and response.
- Extracts user_id from JWT tokens and binds to structlog context.
- Records structured request logs: request_id, user_id, endpoint, status_code, duration.
- Collects Prometheus HTTP metrics (request counts, latency histograms, error counts).
- Handles global exception mapping (DocuFlowException -> RFC 7807).
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.domain.exceptions import DocuFlowException
from app.infrastructure.logging_config import get_logger
from app.infrastructure.observability.metrics import get_metrics
from app.infrastructure.security.tokens import decode_access_token

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects X-Correlation-ID and records structured request telemetry."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        metrics = get_metrics()

        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request_id = correlation_id

        # Extract user_id from Authorization Bearer token if present
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
            try:
                payload = decode_access_token(settings, raw_token)
                user_id = str(payload.get("sub", "anonymous"))
            except Exception:
                user_id = "unauthenticated"

        endpoint = request.url.path
        method = request.method

        # Bind structured context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
        )

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000.0

            # Record Prometheus HTTP Metrics
            metrics.http_requests_total.inc(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            )
            metrics.http_request_duration_seconds.observe(
                duration,
                method=method,
                endpoint=endpoint,
            )

            # Emit required structured request log
            logger.info(
                "request_completed",
                request_id=request_id,
                correlation_id=correlation_id,
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
            )

        response.headers["X-Correlation-ID"] = correlation_id
        return response


def docuflow_exception_handler(request: Request, exc: DocuFlowException) -> JSONResponse:
    """Map DocuFlowException into RFC 7807 Problem Details JSON responses."""
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")
    metrics = get_metrics()

    # Record error metric
    metrics.http_errors_total.inc(
        method=request.method,
        endpoint=request.url.path,
        error_type=exc.error_type,
    )

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
    metrics = get_metrics()

    metrics.http_errors_total.inc(
        method=request.method,
        endpoint=request.url.path,
        error_type="unhandled_server_error",
    )

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
