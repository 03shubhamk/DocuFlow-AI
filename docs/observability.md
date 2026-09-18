# DocuFlow AI — Production Observability Architecture

This document describes the production observability architecture of DocuFlow AI, covering structured logging, metric collection, health probing, distributed tracing, and dashboard visualization.

---

## 1. Structured JSON Logging

DocuFlow AI utilizes `structlog` to emit structured JSON logs in production environments and formatted colored logs in local development.

### HTTP Request Log Schema
Every HTTP request processed through `CorrelationIdMiddleware` outputs a structured log entry:

```json
{
  "event": "http_request_finished",
  "request_id": "4b6f7902-b2f5-46a7-b2f0-256f1dc77da5",
  "user_id": "939c3e98-29dc-4f65-8b8f-3d6118b6e680",
  "endpoint": "/api/v1/documents",
  "method": "POST",
  "status_code": 201,
  "duration_ms": 142.58,
  "client_ip": "192.168.1.10",
  "timestamp": "2026-09-18T12:00:00.142580Z"
}
```

### Celery Processing Job Log Schema
Every background processing job in `parsing_tasks.py` emits structured start, completion, and failure events:

```json
{
  "event": "processing_task_completed",
  "job_id": "c85d85fe-16d7-4c3e-bbbf-77a83d7890f6",
  "document_id": "33b70744-8da0-4cb6-83ca-7cfb72186835",
  "version_id": "5fcf72bb-dcf2-4c28-98e6-764024345260",
  "task_name": "docuflow.parsing.process_document",
  "worker": "celery@worker-node-1",
  "duration": 4.12,
  "duration_ms": 4120.5,
  "status": "COMPLETED",
  "retry_count": 0,
  "error_category": null,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "timestamp": "2026-09-18T12:00:04.262580Z"
}
```

---

## 2. Prometheus Metrics (`/metrics`)

Metrics are exposed at `GET /metrics` and `GET /health/metrics` in Prometheus text exposition format (`text/plain; version=0.0.4`).

### Core Metrics Registry

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total HTTP requests handled |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Latency distribution of HTTP requests |
| `http_errors_total` | Counter | `status_code`, `endpoint` | Total HTTP error responses (4xx, 5xx) |
| `document_uploads_total` | Counter | `mime_type` | Total documents uploaded to platform |
| `document_processing_total` | Counter | `status` | Total document parsing tasks processed |
| `document_processing_failures_total` | Counter | `error_category` | Count of failed document processing runs |
| `document_processing_duration_seconds` | Histogram | None | Time taken for Docling processing |
| `celery_queue_depth` | Gauge | `queue_name` | Current depth of Celery job queues |
| `celery_task_failures_total` | Counter | `task_name`, `error_category` | Total Celery task failures |
| `embedding_generation_duration_seconds` | Histogram | `model` | Latency of chunk embedding generation |
| `qdrant_operation_duration_seconds` | Histogram | `operation` | Latency of vector search / upsert calls |
| `storage_operations_total` | Counter | `operation`, `status` | Total S3 / MinIO storage calls |
| `storage_failures_total` | Counter | `operation`, `error_category` | Storage call failures |

---

## 3. Health & Readiness Probes

The application provides isolated liveness and readiness endpoints:

### `/health/live`
- **Purpose**: Kubernetes / Docker process liveness.
- **Behavior**: Returns `200 OK` (`{"status": "alive"}`) instantly if the event loop is active.

### `/health/ready`
- **Purpose**: Verifies that downstream dependencies (PostgreSQL, Redis, Qdrant, MinIO) are available.
- **Security & Sanitization**: Error details and stack traces are suppressed in API responses to prevent information leakage (e.g. database hostnames or credentials). Diagnostic messages are written exclusively to server-side logs.

Example Response (Healthy):
```json
{
  "status": "healthy",
  "checks": {
    "postgresql": { "status": "ok" },
    "redis": { "status": "ok" },
    "qdrant": { "status": "ok" },
    "minio": { "status": "ok" }
  }
}
```

---

## 4. OpenTelemetry-Compatible Distributed Tracing

DocuFlow AI provides W3C `traceparent`-compliant tracing across the ingestion and query pipeline:

```
[API Request: POST /api/v1/documents]
      │ (W3C traceparent injected in metadata)
      ▼
[Celery Job: docuflow.parsing.process_document]
      │
      ├── [Span: docling.parse_document]
      │         │
      │         └── [Span: chunker.hierarchical_chunk]
      │
      └── [Celery Job: docuflow.indexing.generate_embeddings_and_index]
                │
                ├── [Span: embedding.generate_embeddings]
                │
                └── [Span: qdrant.upsert_vectors]
```

### Context Propagation
The tracer supports:
1. `SpanContext(trace_id, span_id, trace_flags)`
2. `tracer.format_traceparent(context)`: Generates `00-{trace_id}-{span_id}-01`.
3. `tracer.extract_traceparent(header)`: Parses standard W3C `traceparent` headers.
4. `with tracer.start_span("span_name", parent=ctx) as span:`: Context manager managing active span stack, attributes, timing, and error state.

---

## 5. Dashboards & Provisioning

Configuration files are located in `monitoring/`:
- `monitoring/prometheus/prometheus.yml`: Scrapes DocuFlow API on port 8000 every 15s.
- `monitoring/grafana/datasources/prometheus.yml`: Auto-provisions Prometheus datasource.
- `monitoring/grafana/dashboards/dashboards.yml`: Configures dashboard auto-loading.
- `monitoring/grafana/dashboards/docuflow-overview.json`: Ready-to-import Grafana dashboard with panels for request rate, latency quantiles, document throughput, Docling parsing duration, Celery errors, and Qdrant performance.
