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
    qdrant_url: str | None = Field(default=None, description="Optional full Qdrant URL (e.g. https://xyz.qdrant.io)")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_collection_name: str = Field(default="docuflow_chunks")
    qdrant_distance: str = Field(default="Cosine", description="Similarity metric: Cosine, Dot, Euclidean")

    # -------------------------------------------------------------------------
    # Embedding Models & Vector Generation
    # -------------------------------------------------------------------------
    embedding_provider: str = Field(
        default="fastembed",
        description="Embedding backend: fastembed, sentence-transformers, openai, mock",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Model name/identifier for embeddings",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Vector dimensionality (e.g., 384 for bge-small, 768 for bge-base, 1536 for OpenAI)",
    )
    embedding_batch_size: int = Field(default=32, description="Batch size for generating chunk embeddings")
    embedding_api_key: str | None = Field(default=None, description="API key for external embedding providers")

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        allowed = {"fastembed", "sentence-transformers", "openai", "mock", "auto"}
        val = v.lower().strip()
        if val not in allowed:
            raise ValueError(f"embedding_provider must be one of {allowed}")
        return val


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

    # -------------------------------------------------------------------------
    # Docling & OCR Configuration
    # -------------------------------------------------------------------------
    ocr_enabled: bool = Field(default=True, description="Enable OCR for scanned documents and images")
    ocr_provider: str = Field(default="easyocr", description="OCR backend: easyocr, tesseract, rapidocr, none")
    ocr_languages: list[str] = Field(default=["en"], description="List of OCR language codes")
    docling_artifacts_path: str = Field(default="artifacts", description="Sub-path for generated Docling artifacts")
    docling_max_workers: int = Field(default=4, description="Max concurrent threads for Docling conversions")

    @field_validator("ocr_provider")
    @classmethod
    def validate_ocr_provider(cls, v: str) -> str:
        allowed = {"easyocr", "tesseract", "rapidocr", "mac", "none", "auto"}
        val = v.lower()
        if val not in allowed:
            raise ValueError(f"ocr_provider must be one of {allowed}")
        return val

    @field_validator("ocr_languages", mode="before")
    @classmethod
    def parse_ocr_languages(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    # -------------------------------------------------------------------------
    # Intelligent Chunking Configuration
    # -------------------------------------------------------------------------
    chunking_strategy: str = Field(
        default="hierarchical",
        description="Chunking strategy: hierarchical, hybrid, sliding_window",
    )
    chunk_max_tokens: int = Field(default=512, description="Target maximum tokens per chunk")
    chunk_overlap_tokens: int = Field(
        default=64, description="Overlap tokens between adjacent chunks when applicable"
    )
    chunk_min_tokens: int = Field(
        default=30, description="Minimum tokens for merging tiny orphaned chunks"
    )
    chunk_preserve_tables: bool = Field(
        default=True, description="Preserve structured tables intact or chunk row-wise"
    )

    @field_validator("chunking_strategy")
    @classmethod
    def validate_chunking_strategy(cls, v: str) -> str:
        allowed = {"hierarchical", "hybrid", "sliding_window"}
        val = v.lower()
        if val not in allowed:
            raise ValueError(f"chunking_strategy must be one of {allowed}")
        return val

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
