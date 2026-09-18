"""
DocuFlow AI — Parsing Tasks (Celery Background Worker).

Executes asynchronous document intelligence processing using Docling and vector indexing in Qdrant.
Captures execution progress, persists derivative artifacts, records structured observability metrics,
and traces task execution across the document lifecycle.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog

from app.config import get_settings
from app.infrastructure.database.session import build_engine, build_session_factory
from app.infrastructure.observability import get_metrics, tracer
from app.infrastructure.processors import get_document_processor
from app.infrastructure.storage import get_storage
from app.infrastructure.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)
_settings = get_settings()

_session_factory_override: Any = None


def set_task_session_factory(factory: Any) -> None:
    """Set custom session factory for test isolation."""
    global _session_factory_override
    _session_factory_override = factory


def _categorize_error(exc: Exception) -> str:
    """Classifies an exception into standard error categories for metrics and logs."""
    text = (type(exc).__name__ + " " + str(exc)).lower()
    if "validation" in text or "valueerror" in text:
        return "validation_error"
    if "timeout" in text or "timeouterror" in text:
        return "timeout"
    if "connection" in text or "db" in text or "sql" in text:
        return "database_error"
    if "permission" in text or "auth" in text:
        return "security_error"
    if "docling" in text or "parse" in text or "parsing" in text:
        return "parsing_error"
    return "internal_error"



@celery_app.task(
    name="docuflow.parsing.process_document",
    bind=True,
    max_retries=_settings.celery_task_max_retries,
    default_retry_delay=_settings.celery_task_default_retry_delay,
    retry_backoff=True,
    retry_backoff_max=_settings.celery_task_retry_backoff_max,
    acks_late=True,
)
def process_document_task(
    self,
    job_id: str,
    document_id: str,
    version_id: str,
    parent_traceparent: str | None = None,
) -> dict[str, str]:
    """Celery background worker executing Docling document parsing pipeline with full telemetry."""
    task_name = "docuflow.parsing.process_document"
    worker_name = getattr(self.request, "hostname", None) or "celery-worker"
    retry_count = self.request.retries
    start_time = time.perf_counter()
    metrics = get_metrics()

    span_context = tracer.extract_traceparent(parent_traceparent) if parent_traceparent else None

    with tracer.start_span("celery.process_document", parent=span_context) as span:
        span.set_attribute("job_id", job_id)
        span.set_attribute("document_id", document_id)
        span.set_attribute("version_id", version_id)
        span.set_attribute("worker", worker_name)
        span.set_attribute("task_name", task_name)

        logger.info(
            "processing_task_started",
            job_id=job_id,
            document_id=document_id,
            version_id=version_id,
            task_name=task_name,
            worker=worker_name,
            retry_count=retry_count,
            trace_id=span.context.trace_id,
        )

        async def _run_async_pipeline() -> dict[str, Any]:
            from app.application.documents.service import DocumentService

            storage = get_storage()
            processor = get_document_processor()

            if _session_factory_override is not None:
                async with _session_factory_override() as session:
                    service = DocumentService(session=session, storage=storage, processor=processor)
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
            else:
                settings = get_settings()
                engine = build_engine(settings, use_null_pool=True)
                session_factory = build_session_factory(engine)
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
                    res = future.result()
            else:
                res = asyncio.run(_run_async_pipeline())

            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000.0, 2)

            metrics.document_processing_total.inc(labels={"status": "completed"})
            metrics.document_processing_duration_seconds.observe(duration_s)

            logger.info(
                "processing_task_completed",
                job_id=job_id,
                document_id=document_id,
                version_id=version_id,
                task_name=task_name,
                worker=worker_name,
                duration=duration_s,
                duration_ms=duration_ms,
                status="COMPLETED",
                retry_count=retry_count,
                error_category=None,
                trace_id=span.context.trace_id,
            )
            return res

        except Exception as exc:
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000.0, 2)
            error_cat = _categorize_error(exc)

            span.set_attribute("error", True)
            span.set_attribute("error_category", error_cat)

            metrics.document_processing_total.inc(labels={"status": "failed"})
            metrics.document_processing_failures_total.inc(labels={"error_category": error_cat})
            metrics.celery_task_failures_total.inc(labels={"task_name": task_name, "error_category": error_cat})

            logger.error(
                "processing_task_failed",
                job_id=job_id,
                document_id=document_id,
                version_id=version_id,
                task_name=task_name,
                worker=worker_name,
                duration=duration_s,
                duration_ms=duration_ms,
                status="FAILED",
                retry_count=retry_count,
                error_category=error_cat,
                error=str(exc),
                trace_id=span.context.trace_id,
            )

            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5) from exc
            raise exc


@celery_app.task(
    name="docuflow.indexing.generate_embeddings_and_index",
    bind=True,
    max_retries=_settings.celery_task_max_retries,
    default_retry_delay=_settings.celery_task_default_retry_delay,
    retry_backoff=True,
    retry_backoff_max=_settings.celery_task_retry_backoff_max,
    acks_late=True,
)
def generate_embeddings_and_index_task(
    self,
    job_id: str,
    document_id: str,
    version_id: str,
    parent_traceparent: str | None = None,
) -> dict[str, str]:
    """Celery background worker generating embeddings and indexing chunks into Qdrant with full telemetry."""
    task_name = "docuflow.indexing.generate_embeddings_and_index"
    worker_name = getattr(self.request, "hostname", None) or "celery-worker"
    retry_count = self.request.retries
    start_time = time.perf_counter()
    metrics = get_metrics()

    span_context = tracer.extract_traceparent(parent_traceparent) if parent_traceparent else None

    with tracer.start_span("celery.generate_embeddings_and_index", parent=span_context) as span:
        span.set_attribute("job_id", job_id)
        span.set_attribute("document_id", document_id)
        span.set_attribute("version_id", version_id)
        span.set_attribute("worker", worker_name)
        span.set_attribute("task_name", task_name)

        logger.info(
            "indexing_task_started",
            job_id=job_id,
            document_id=document_id,
            version_id=version_id,
            task_name=task_name,
            worker=worker_name,
            retry_count=retry_count,
            trace_id=span.context.trace_id,
        )

        async def _run_async_indexing() -> dict[str, Any]:
            from app.application.documents.service import DocumentService
            from app.domain.entities import User, UserRole

            storage = get_storage()
            processor = get_document_processor()

            if _session_factory_override is not None:
                async with _session_factory_override() as session:
                    service = DocumentService(session=session, storage=storage, processor=processor)
                    doc = await service.document_repo.get_by_id(uuid.UUID(document_id))
                    if not doc:
                        return {"status": "FAILED", "reason": "Document not found"}
                    synthetic_user = User(
                        id=doc.owner_id,
                        tenant_id=doc.tenant_id,
                        email="system@internal",
                        hashed_password="",
                        full_name="System Background Worker",
                        role=UserRole.ADMIN,
                    )
                    res = await service.reindex_document(
                        document_id=uuid.UUID(document_id),
                        current_user=synthetic_user,
                    )
                    return {
                        "status": "COMPLETED",
                        "job_id": job_id,
                        "document_id": document_id,
                        "version_id": version_id,
                        "chunks_indexed": str(res.chunks_indexed),
                    }
            else:
                settings = get_settings()
                engine = build_engine(settings, use_null_pool=True)
                session_factory = build_session_factory(engine)
                async with session_factory() as session:
                    service = DocumentService(session=session, storage=storage, processor=processor)
                    try:
                        doc = await service.document_repo.get_by_id(uuid.UUID(document_id))
                        if not doc:
                            return {"status": "FAILED", "reason": "Document not found"}
                        synthetic_user = User(
                            id=doc.owner_id,
                            tenant_id=doc.tenant_id,
                            email="system@internal",
                            hashed_password="",
                            full_name="System Background Worker",
                            role=UserRole.ADMIN,
                        )
                        res = await service.reindex_document(
                            document_id=uuid.UUID(document_id),
                            current_user=synthetic_user,
                        )
                        return {
                            "status": "COMPLETED",
                            "job_id": job_id,
                            "document_id": document_id,
                            "version_id": version_id,
                            "chunks_indexed": str(res.chunks_indexed),
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
                    future = pool.submit(lambda: asyncio.run(_run_async_indexing()))
                    res = future.result()
            else:
                res = asyncio.run(_run_async_indexing())

            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000.0, 2)

            logger.info(
                "indexing_task_completed",
                job_id=job_id,
                document_id=document_id,
                version_id=version_id,
                task_name=task_name,
                worker=worker_name,
                duration=duration_s,
                duration_ms=duration_ms,
                status="COMPLETED",
                retry_count=retry_count,
                error_category=None,
                trace_id=span.context.trace_id,
            )
            return res

        except Exception as exc:
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000.0, 2)
            error_cat = _categorize_error(exc)

            span.set_attribute("error", True)
            span.set_attribute("error_category", error_cat)

            metrics.celery_task_failures_total.inc(labels={"task_name": task_name, "error_category": error_cat})

            logger.error(
                "indexing_task_failed",
                job_id=job_id,
                document_id=document_id,
                version_id=version_id,
                task_name=task_name,
                worker=worker_name,
                duration=duration_s,
                duration_ms=duration_ms,
                status="FAILED",
                retry_count=retry_count,
                error_category=error_cat,
                error=str(exc),
                trace_id=span.context.trace_id,
            )

            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5) from exc
            raise exc



