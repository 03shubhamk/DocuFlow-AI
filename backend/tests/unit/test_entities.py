"""Unit tests for domain entities."""

from __future__ import annotations

import uuid

from app.domain.entities import (
    ProcessingJob,
    ProcessingStatus,
    UserRole,
)


class TestProcessingJob:
    def test_can_retry_when_under_max(self):
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status=ProcessingStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        assert job.can_retry() is True

    def test_cannot_retry_when_at_max(self):
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status=ProcessingStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        assert job.can_retry() is False

    def test_can_cancel_when_queued(self):
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status=ProcessingStatus.QUEUED,
        )
        assert job.can_cancel() is True

    def test_cannot_cancel_when_completed(self):
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            status=ProcessingStatus.COMPLETED,
        )
        assert job.can_cancel() is False


class TestProcessingStatus:
    def test_all_statuses_exist(self):
        expected = {
            "UPLOADED",
            "QUEUED",
            "PROCESSING",
            "CHUNKING",
            "EMBEDDING",
            "INDEXING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }
        actual = {s.value for s in ProcessingStatus}
        assert actual == expected


class TestUserRole:
    def test_roles(self):
        assert UserRole.ADMIN.value == "ADMIN"
        assert UserRole.EDITOR.value == "EDITOR"
        assert UserRole.VIEWER.value == "VIEWER"
