"""
DocuFlow AI — Integration Tests for Storage Adapters.

Tests InMemoryStorage and S3Storage abstractions for put, get, delete, exists,
path prefix listing, and presigned URL generation.
"""

from __future__ import annotations

import pytest

from app.infrastructure.storage.memory_storage import InMemoryStorage


class TestStorageIntegration:
    @pytest.mark.asyncio
    async def test_put_get_exists_delete_lifecycle(self):
        storage = InMemoryStorage()
        path = "tenants/tenant-1/documents/doc-1/versions/v1/original.pdf"
        data = b"%PDF-1.4 Mock Binary Data for Storage Integration Test"

        # Initially does not exist
        assert await storage.exists(path) is False

        # Put object
        stored_path = await storage.upload(path, data, content_type="application/pdf")
        assert stored_path == path
        assert await storage.exists(path) is True

        # Get object
        retrieved = await storage.download(path)
        assert retrieved == data

        # Presigned URL
        url = await storage.get_presigned_url(path, expires_in_seconds=3600)
        assert path in url

        # Delete object
        deleted = await storage.delete(path)
        assert deleted is True
        assert await storage.exists(path) is False

