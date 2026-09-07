"""
DocuFlow AI — FastAPI Application Factory.

Builds and configures the FastAPI application with:
- Structured logging
- Middleware (correlation ID, CORS, security headers)
- API v1 router (/api/v1)
- Health check routes (/health)
- Global exception handlers (RFC 7807)
- Lifespan events (startup / shutdown)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import (
    CorrelationIdMiddleware,
    docuflow_exception_handler,
    unhandled_exception_handler,
)
from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.domain.exceptions import DocuFlowException
from app.infrastructure.logging_config import configure_logging, get_logger

settings = get_settings()

# Configure structured logging as the first action
configure_logging(log_level=settings.log_level, environment=settings.environment)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown event handlers."""
    logger.info(
        "docuflow_startup",
        project=settings.project_name,
        environment=settings.environment,
        api_version="v1",
    )
    yield
    logger.info("docuflow_shutdown", project=settings.project_name)


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title=settings.project_name,
        description=(
            "Production-grade Document Intelligence and AI Ingestion Platform. "
            "Powered by Docling, Qdrant, and FastAPI."
        ),
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware (order matters — outermost first)
    # ------------------------------------------------------------------
    app.add_middleware(CorrelationIdMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    # ------------------------------------------------------------------
    # Exception Handlers
    # ------------------------------------------------------------------
    app.add_exception_handler(DocuFlowException, docuflow_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    # Health at root — reachable before /api/v1 prefix
    app.include_router(health_router)

    # All versioned API routes under /api/v1
    app.include_router(api_router, prefix=settings.api_v1_str)

    return app


app = create_app()
