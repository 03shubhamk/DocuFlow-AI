"""
DocuFlow AI — FastAPI Application Factory & Security Architecture.

Builds and configures the FastAPI application with:
- Structured logging & sensitive data redaction
- Middleware pipeline:
  1. Correlation ID tracking (X-Correlation-ID)
  2. OWASP Security Headers (CSP, HSTS, X-Content-Type-Options)
  3. Maximum Request Body Size enforcement (DoS protection)
  4. Token Bucket Rate Limiting (per IP & Auth token)
  5. Strict CORS Configuration
- API v1 router (/api/v1)
- Health check routes (/health)
- Global exception handlers (RFC 7807 Problem Details)
- Lifespan events (startup / shutdown)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import (
    CorrelationIdMiddleware,
    docuflow_exception_handler,
    unhandled_exception_handler,
)
from app.api.security_middleware import (
    MaxBodySizeMiddleware,
    RateLimitingMiddleware,
    SecurityHeadersMiddleware,
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

    if "sqlite" in settings.database_url:
        try:
            import uuid
            from sqlalchemy import select
            from app.infrastructure.database.models import Base, TenantModel, UserModel
            from app.infrastructure.database.session import build_engine, build_session_factory
            from app.infrastructure.security.tokens import hash_password

            engine = build_engine(settings)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            session_factory = build_session_factory(engine)
            async with session_factory() as session:
                # 1. Ensure default tenant exists
                result_t = await session.execute(
                    select(TenantModel).where(TenantModel.slug == "default-tenant")
                )
                default_tenant = result_t.scalar_one_or_none()
                if not default_tenant:
                    default_tenant = TenantModel(
                        id=uuid.uuid4(),
                        name="Default Organization",
                        slug="default-tenant",
                        is_active=True,
                    )
                    session.add(default_tenant)
                    await session.flush()

                # 2. Ensure demo users exist
                result_u = await session.execute(
                    select(UserModel).where(UserModel.email == "admin@docuflow.ai")
                )
                if not result_u.scalar_one_or_none():
                    admin = UserModel(
                        id=uuid.uuid4(),
                        email="admin@docuflow.ai",
                        hashed_password=hash_password("DocuFlow2026!Secure"),
                        full_name="System Administrator",
                        role="ADMIN",
                        tenant_id=default_tenant.id,
                        is_active=True,
                    )
                    analyst = UserModel(
                        id=uuid.uuid4(),
                        email="analyst@docuflow.ai",
                        hashed_password=hash_password("Analyst2026!Secure"),
                        full_name="Senior Document Analyst",
                        role="USER",
                        tenant_id=default_tenant.id,
                        is_active=True,
                    )
                    session.add_all([admin, analyst])
                    await session.commit()
                    logger.info("demo_users_seeded", users=["admin@docuflow.ai", "analyst@docuflow.ai"])
        except Exception as exc:
            logger.warning("sqlite_init_failed", error=str(exc))

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
    # Middleware Pipeline (order matters — outermost first)
    # ------------------------------------------------------------------
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaxBodySizeMiddleware)
    app.add_middleware(RateLimitingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "Retry-After"],
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

    # Prometheus exposition format at root /metrics
    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        from fastapi import Response as PlainResponse

        from app.infrastructure.observability import get_metrics

        return PlainResponse(
            content=get_metrics().generate_prometheus_output(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # All versioned API routes under /api/v1
    app.include_router(api_router, prefix=settings.api_v1_str)

    return app


app = create_app()

