# ADR 0003: Celery and Redis for Asynchronous Ingestion Pipeline

**Status:** Accepted  
**Date:** 2026-09-06  
**Deciders:** Principal Software Architect, Backend Team  
**Consulted:** DevOps  
**Informed:** Stakeholders  

---

## 1. Context & Problem Statement

Document parsing via Docling, OCR execution, TableFormer inference, and dense vector generation are computationally demanding operations. A 50-page financial report with multiple scanned tables can take 15 to 60 seconds to process.

Attempting to process documents synchronously within an HTTP request-response cycle leads to:
- HTTP client timeouts (504 Gateway Timeout).
- Starvation of the web server thread/worker pool, causing the API to become unresponsive to other users.
- Loss of in-flight jobs if the client disconnects or if the web process restarts.

We must decouple document upload from document processing using a resilient, distributed asynchronous task queue.

---

## 2. Decision Drivers

- **Non-Blocking User Experience**: The API must immediately accept the file upload (< 500ms) and return a tracking job ID.
- **Robust Orchestration**: Capability to coordinate multi-stage workflows (Parse -> Export -> Chunk -> Embed -> Index) with canvas primitives.
- **Independent Autoscaling**: The ability to scale CPU-heavy parser workers independently from I/O-heavy vector indexing workers.
- **Resilience & Fault Recovery**: Built-in retries with exponential backoff, dead-letter tracking, and task cancellation.

---

## 3. Considered Options

1. **FastAPI BackgroundTasks**: Runs within the web server process; tasks are lost on container restart; no distributed queuing or multi-worker concurrency.
2. **ARQ / SAQ (Asyncio + Redis)**: Lightweight, but lacks rich workflow canvas primitives (`chain`, `chord`, `group`) and mature tooling for enterprise monitoring.
3. **Temporal / Cadence**: Extremely robust for complex microservice sagas, but introduces substantial architectural complexity, extra servers, and operational overhead unnecessary for a modular monolith.
4. **Celery with Redis Broker**: The industry-standard Python distributed task queue with native Redis support, Celery Canvas workflow primitives, exponential retry backoff, and widespread operational familiarity.

---

## 4. Decision Outcome

**Chosen Option:** Option 4 — **Celery with Redis Broker and Result Backend**.

We deploy Celery with Redis for distributed task execution, partitioning tasks across dedicated queues:
- `docuflow.parsing`: For heavy Docling parsing and OCR (low worker concurrency to prevent RAM exhaustion).
- `docuflow.indexing`: For hierarchical chunking, vector generation, and Qdrant ingestion (higher concurrency).
- `docuflow.maintenance`: For background cleanup of soft-deleted documents.

### Positive Consequences
- **Complete Decoupling**: API servers remain fast and responsive, serving client queries without being blocked by document ingestion.
- **Idempotent Canvas Chains**: Pipelines are structured using `celery.chain`, where each stage passes state checkpoints to the next.
- **Granular Retries**: Transient storage or network errors trigger automatic retries with exponential backoff and jitter without re-running the entire pipeline.
- **Task Revocation**: Active jobs can be aborted by admins or users via Celery's task revocation signals.

### Negative Consequences
- **Operational Footprint**: Requires running Redis and separate Celery worker processes alongside the API server.
- **Process Memory Leaks**: PyTorch and OCR libraries can retain native memory over time. 
- **Mitigation**: Workers are configured with `worker_max_tasks_per_child = 50` and `worker_max_memory_per_child = 1048576` (1 GB) to automatically recycle worker processes after processing batches of documents.
