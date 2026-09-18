"""
DocuFlow AI — Celery Application.

Defines the Celery worker application, queue configuration,
and task routing. No processing tasks are implemented here yet
(Phase 4). This foundation enables the worker container to start.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "docuflow",
    broker=_settings.redis_url,
    backend=_settings.celery_result_backend,
    include=[
        # Phase 4: parsing and indexing tasks will be added here
        # "app.infrastructure.tasks.parsing_tasks",
        # "app.infrastructure.tasks.indexing_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Retry & visibility
    broker_transport_options={"visibility_timeout": 3600},
    task_acks_late=True,
    worker_prefetch_multiplier=_settings.celery_worker_prefetch_multiplier,
    worker_concurrency=_settings.celery_worker_concurrency,
    task_time_limit=_settings.celery_task_time_limit,
    task_soft_time_limit=_settings.celery_task_soft_time_limit,
    # Worker memory recycling (prevents memory bloat across OCR/Docling runs)
    worker_max_tasks_per_child=_settings.celery_worker_max_tasks_per_child,
    # Queue definitions
    task_queues={
        "docuflow.parsing": {"exchange": "docuflow.parsing", "routing_key": "parsing"},
        "docuflow.indexing": {"exchange": "docuflow.indexing", "routing_key": "indexing"},
        "celery": {"exchange": "celery", "routing_key": "celery"},
    },
    task_default_queue="celery",
    task_default_exchange="celery",
    task_default_routing_key="celery",
)
