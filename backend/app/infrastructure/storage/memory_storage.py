"""
DocuFlow AI — In-Memory Object Storage Implementation.

Used for fast, deterministic unit testing and local development without external dependencies.
"""

from __future__ import annotations

import asyncio
from typing import BinaryIO

from app.domain.exceptions import StorageException
from app.infrastructure.storage.base import ObjectStorage


class InMemoryStorage(ObjectStorage):
    """Thread-safe in-memory mock implementation of ObjectStorage."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._metadata: dict[str, dict[str, str]] = {}
        self._content_types: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.should_fail: bool = False  # Allows simulating storage failures in tests

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        if self.should_fail:
            raise StorageException(f"Simulated storage failure while uploading '{key}'")

        async with self._lock:
            if isinstance(data, bytes):
                raw_bytes = data
            else:
                raw_bytes = data.read()

            self._store[key] = raw_bytes
            self._content_types[key] = content_type
            if metadata:
                self._metadata[key] = metadata.copy()
            return key

    async def download(self, key: str) -> bytes:
        if self.should_fail:
            raise StorageException(f"Simulated storage failure while downloading '{key}'")

        async with self._lock:
            if key not in self._store:
                raise StorageException(f"Object '{key}' not found in in-memory storage.")
            return self._store[key]

    async def delete(self, key: str) -> bool:
        if self.should_fail:
            raise StorageException(f"Simulated storage failure while deleting '{key}'")

        async with self._lock:
            if key in self._store:
                del self._store[key]
                self._content_types.pop(key, None)
                self._metadata.pop(key, None)
                return True
            return False

    async def exists(self, key: str) -> bool:
        async with self._lock:
            return key in self._store

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        async with self._lock:
            if key not in self._store:
                raise StorageException(f"Object '{key}' not found.")
            return f"https://mock-storage.local/{key}?expires={expires_in_seconds}"

    def clear(self) -> None:
        """Clear all stored objects."""
        self._store.clear()
        self._content_types.clear()
        self._metadata.clear()
        self.should_fail = False
