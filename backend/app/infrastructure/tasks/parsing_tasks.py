"""
DocuFlow AI — Parsing Tasks (Celery / Background Worker Dispatcher).

Provides asynchronous ingestion pipeline task stubs.
"""

from __future__ import annotations

import structlog

from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="docuflow.parsing.process_document", bind=True, max_retries=3)
def process_document_task(self, job_id: str, document_id: str) -> dict[str, str]:
    """Asynchronously process an uploaded document (Docling parsing in Phase 4)."""
    logger.info("processing_task_started", job_id=job_id, document_id=document_id)
    # Stub: will be executed by Celery worker with Docling in Phase 4
    return {"status": "QUEUED", "job_id": job_id, "document_id": document_id}
