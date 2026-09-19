"""
DocuFlow AI — Local FileSystem Object Storage Implementation.

Provides persistent file-backed object storage on the local disk for local development
and testing when MinIO/S3 is not running.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import BinaryIO

from app.domain.exceptions import StorageException
from app.infrastructure.storage.base import ObjectStorage


class LocalFileSystemStorage(ObjectStorage):
    """File-system backed ObjectStorage for standalone local development."""

    def __init__(self, base_dir: str | Path = "./data/storage") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _get_path(self, key: str) -> Path:
        clean_key = key.lstrip("/\\")
        full_path = (self.base_dir / clean_key).resolve()
        # Prevent directory traversal
        if not str(full_path).startswith(str(self.base_dir)):
            raise StorageException(f"Invalid storage key path: '{key}'")
        return full_path

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            target_path = self._get_path(key)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(data, bytes):
                raw_bytes = data
            else:
                raw_bytes = data.read()

            async with self._lock:
                target_path.write_bytes(raw_bytes)

            return key
        except Exception as exc:
            raise StorageException(f"Failed to save local file for key '{key}': {exc}") from exc

    async def download(self, key: str) -> bytes:
        try:
            target_path = self._get_path(key)
            if not target_path.exists() or not target_path.is_file():
                raise StorageException(f"Object '{key}' not found on local storage.")
            return target_path.read_bytes()
        except Exception as exc:
            if isinstance(exc, StorageException):
                raise
            raise StorageException(f"Failed to read local file for key '{key}': {exc}") from exc

    async def delete(self, key: str) -> bool:
        try:
            target_path = self._get_path(key)
            if target_path.exists() and target_path.is_file():
                target_path.unlink()
                return True
            return False
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        target_path = self._get_path(key)
        return target_path.exists() and target_path.is_file()

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        target_path = self._get_path(key)
        if not target_path.exists():
            raise StorageException(f"Object '{key}' not found on local storage.")
        return f"/api/v1/documents/download/{key}"
