"""
DocuFlow AI — Object Storage Abstract Base Class.

Defines the contract for all storage backends (MinIO, AWS S3, MemoryStorage).
Ensures business logic remains completely decoupled from specific storage providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class ObjectStorage(ABC):
    """Abstract interface for object storage providers."""

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload an object and return its storage key/URI.

        Args:
            key: Target object key/path in storage.
            data: Raw bytes or binary file stream to upload.
            content_type: MIME content type of the object.
            metadata: Optional user-defined metadata dictionary.

        Returns:
            The stored object key.
        """

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download and return raw bytes of the object.

        Args:
            key: Object key/path in storage.

        Returns:
            Raw bytes of the object.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an object from storage.

        Args:
            key: Object key/path to delete.

        Returns:
            True if deleted successfully.
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if an object exists at the given key.

        Args:
            key: Object key/path to check.

        Returns:
            True if object exists, False otherwise.
        """

    @abstractmethod
    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        """Generate a presigned GET URL for temporary direct access.

        Args:
            key: Object key/path.
            expires_in_seconds: Validity duration in seconds.

        Returns:
            Presigned download URL.
        """
