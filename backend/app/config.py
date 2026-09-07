"""
DocuFlow AI — Application Configuration.

Uses Pydantic Settings to validate and load all environment variables.
Application will refuse to start if required settings are missing or invalid.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    environment: str = Field(default="development", description="Runtime environment")
    project_name: str = Field(default="DocuFlow AI")
    api_v1_str: str = Field(default="/api/v1")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "testing"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    # -------------------------------------------------------------------------
    # Database — PostgreSQL
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/docuflow",
        description="Async SQLAlchemy database URL (postgresql+asyncpg://...)",
    )
    database_sync_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/docuflow",
        description="Synchronous PostgreSQL URL used by Alembic migrations",
    )
    db_pool_size: int = Field(default=20)
    db_max_overflow: int = Field(default=10)
    db_pool_timeout: int = Field(default=30)
    db_pool_recycle: int = Field(default=1800)

    # -------------------------------------------------------------------------
    # Redis & Celery
    # -------------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    # -------------------------------------------------------------------------
    # Object Storage — S3 / MinIO
    # -------------------------------------------------------------------------
    s3_endpoint_url: str | None = Field(default="http://localhost:9000")
    s3_access_key_id: str = Field(default="minioadmin", description="S3 / MinIO access key")
    s3_secret_access_key: str = Field(default="minioadmin", description="S3 / MinIO secret key")
    s3_bucket_documents: str = Field(default="docuflow-documents")
    s3_region: str = Field(default="us-east-1")
    s3_secure: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # Qdrant Vector Database
    # -------------------------------------------------------------------------
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="docuflow_chunks")

    # -------------------------------------------------------------------------
    # Security — JWT
    # -------------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="dev-jwt-secret-key-at-least-32-chars-long-docuflow-platform",
        description="Secret key for signing JWT tokens",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return v

    # -------------------------------------------------------------------------
    # File Upload Constraints
    # -------------------------------------------------------------------------
    max_upload_size_bytes: int = Field(default=52_428_800)  # 50 MB
    allowed_mime_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/html",
            "text/markdown",
            "text/plain",
            "image/png",
            "image/jpeg",
            "image/tiff",
        ]
    )

    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def parse_mime_types(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Cached so settings object is instantiated once per process.
    """
    return Settings()
