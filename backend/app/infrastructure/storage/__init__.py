"""
DocuFlow AI — Storage Infrastructure Package.

Provides storage abstractions and singleton factory for S3, MinIO, and InMemory storage.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.storage.base import ObjectStorage
from app.infrastructure.storage.memory_storage import InMemoryStorage
from app.infrastructure.storage.minio_storage import MinIOStorage
from app.infrastructure.storage.s3_storage import S3Storage

__all__ = [
    "ObjectStorage",
    "S3Storage",
    "MinIOStorage",
    "InMemoryStorage",
    "get_storage",
]


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    """Factory creating and caching the configured ObjectStorage backend."""
    settings = get_settings()

    if settings.environment == "testing":
        return InMemoryStorage()

    if settings.s3_endpoint_url:
        return MinIOStorage(
            bucket_name=settings.s3_bucket_documents,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_secure,
        )

    return S3Storage(
        bucket_name=settings.s3_bucket_documents,
        endpoint_url=None,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_secure,
    )
