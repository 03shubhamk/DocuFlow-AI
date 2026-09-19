"""
DocuFlow AI — Storage Infrastructure Package.

Provides storage abstractions and singleton factory for S3, MinIO, and InMemory storage.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.storage.base import ObjectStorage
from app.infrastructure.storage.local_storage import LocalFileSystemStorage
from app.infrastructure.storage.memory_storage import InMemoryStorage
from app.infrastructure.storage.minio_storage import MinIOStorage
from app.infrastructure.storage.s3_storage import S3Storage

__all__ = [
    "ObjectStorage",
    "S3Storage",
    "MinIOStorage",
    "InMemoryStorage",
    "LocalFileSystemStorage",
    "get_storage",
]


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    """Factory creating and caching the configured ObjectStorage backend."""
    settings = get_settings()

    backend = getattr(settings, "storage_backend", "auto").lower()

    if backend == "memory" or settings.environment == "testing":
        return InMemoryStorage()

    if backend in {"local", "filesystem"}:
        return LocalFileSystemStorage()

    if backend == "minio" or (backend == "auto" and settings.s3_endpoint_url):
        # In development mode, check if MinIO is actually responding on the endpoint
        if settings.environment == "development" and backend == "auto":
            import socket
            from urllib.parse import urlparse
            try:
                parsed = urlparse(settings.s3_endpoint_url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or (443 if parsed.scheme == "https" else 9000)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((host, port))
                sock.close()
                if result != 0:
                    # MinIO is not running locally, seamlessly fallback to local filesystem storage
                    return LocalFileSystemStorage()
            except Exception:
                return LocalFileSystemStorage()

        return MinIOStorage(
            bucket_name=settings.s3_bucket_documents,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_secure,
        )

    if backend == "s3":
        return S3Storage(
            bucket_name=settings.s3_bucket_documents,
            endpoint_url=None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_secure,
        )

    return LocalFileSystemStorage()
