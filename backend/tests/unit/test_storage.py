"""
DocuFlow AI — Unit Tests for Storage Layer Abstractions.

Tests InMemoryStorage, S3Storage operations, error handling, and failure simulation.
"""

from __future__ import annotations

import io

import pytest

from app.domain.exceptions import StorageException
from app.infrastructure.storage.memory_storage import InMemoryStorage


@pytest.mark.asyncio
async def test_in_memory_storage_upload_and_download() -> None:
    storage = InMemoryStorage()
    content = b"Sample document payload content for storage testing."
    key = "tenants/t1/documents/d1/v1/doc.pdf"

    saved_key = await storage.upload(
        key=key,
        data=content,
        content_type="application/pdf",
        metadata={"tenant_id": "t1"},
    )
    assert saved_key == key

    assert await storage.exists(key) is True
    assert await storage.exists("nonexistent/key") is False

    downloaded = await storage.download(key)
    assert downloaded == content


@pytest.mark.asyncio
async def test_in_memory_storage_upload_from_stream() -> None:
    storage = InMemoryStorage()
    content = b"Binary stream content."
    stream = io.BytesIO(content)
    key = "tenants/t1/documents/d1/v1/stream.docx"

    await storage.upload(
        key=key,
        data=stream,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    downloaded = await storage.download(key)
    assert downloaded == content


@pytest.mark.asyncio
async def test_in_memory_storage_delete() -> None:
    storage = InMemoryStorage()
    key = "tenants/t1/documents/d1/v1/delete_me.txt"
    await storage.upload(key=key, data=b"Delete this", content_type="text/plain")

    assert await storage.exists(key) is True
    deleted = await storage.delete(key)
    assert deleted is True
    assert await storage.exists(key) is False

    # Deleting non-existent returns False
    assert await storage.delete("nonexistent") is False


@pytest.mark.asyncio
async def test_in_memory_storage_download_nonexistent_raises() -> None:
    storage = InMemoryStorage()
    with pytest.raises(StorageException) as exc_info:
        await storage.download("missing/key")
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_in_memory_storage_presigned_url() -> None:
    storage = InMemoryStorage()
    key = "tenants/t1/documents/d1/v1/file.pdf"
    await storage.upload(key=key, data=b"Test", content_type="application/pdf")

    url = await storage.get_presigned_url(key, expires_in_seconds=1800)
    assert "mock-storage.local" in url
    assert key in url


@pytest.mark.asyncio
async def test_in_memory_storage_failure_simulation() -> None:
    storage = InMemoryStorage()
    storage.should_fail = True

    with pytest.raises(StorageException):
        await storage.upload("test", b"data", "text/plain")

    with pytest.raises(StorageException):
        await storage.download("test")

    with pytest.raises(StorageException):
        await storage.delete("test")
