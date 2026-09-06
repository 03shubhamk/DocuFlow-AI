"""
DocuFlow AI — Domain Gateway Interfaces (Ports).

Abstract base classes defining the contracts that infrastructure adapters must fulfill.
The Domain layer depends only on these interfaces, never on concrete implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, BinaryIO
from uuid import UUID


class StorageGateway(ABC):
    """Port for object storage operations (S3 / MinIO)."""

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload an object and return the storage key."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download an object by key and return its bytes."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object by key."""

    @abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expiry_seconds: int = 900,
    ) -> str:
        """Generate a time-limited presigned download URL."""

    @abstractmethod
    async def object_exists(self, key: str) -> bool:
        """Return True if an object with the given key exists."""


class MalwareScannerGateway(ABC):
    """Port for malware scanning of uploaded files.

    Implementations may integrate with ClamAV, commercial AV vendors,
    or provide a passthrough no-op scanner for development.
    """

    @abstractmethod
    async def scan(self, data: bytes) -> bool:
        """Scan file bytes for malware.

        Returns:
            True if file is clean, False if a threat is detected.
        """


class AuditLoggerGateway(ABC):
    """Port for writing immutable audit log events."""

    @abstractmethod
    async def record(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit event."""
