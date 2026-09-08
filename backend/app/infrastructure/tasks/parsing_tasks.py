"""
DocuFlow AI — Parsing Tasks (Celery Background Worker).

Executes asynchronous document intelligence processing using Docling.
Captures execution progress, persists derivative artifacts, and records errors on failure.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.config import get_settings
from app.infrastructure.database.session import build_engine, build_session_factory
from app.infrastructure.processors import get_document_processor
from app.infrastructure.storage import get_storage
from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="docuflow.parsing.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_document_task(
    self,
    job_id: str,
    document_id: str,
    version_id: str,
) -> dict[str, str]:
    """Celery background worker executing Docling document parsing pipeline."""
    logger.info("processing_task_started", job_id=job_id, document_id=document_id, version_id=version_id)

    async def _run_async_pipeline() -> dict[str, str]:
        from app.application.documents.service import DocumentService

        settings = get_settings()
        engine = build_engine(settings)
        session_factory = build_session_factory(engine)
        storage = get_storage()
        processor = get_document_processor()

        async with session_factory() as session:
            service = DocumentService(session=session, storage=storage, processor=processor)
            try:
                processed = await service.process_document_version(
                    document_id=uuid.UUID(document_id),
                    version_id=uuid.UUID(version_id),
                )
                return {
                    "status": "COMPLETED",
                    "job_id": job_id,
                    "document_id": document_id,
                    "version_id": version_id,
                    "duration_ms": str(processed.duration_ms),
                }
            finally:
                await engine.dispose()

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(_run_async_pipeline()))
                return future.result()
        else:
            return asyncio.run(_run_async_pipeline())

    except Exception as exc:
        logger.error(
            "processing_task_failed",
            job_id=job_id,
            document_id=document_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5) from exc
        raise exc

