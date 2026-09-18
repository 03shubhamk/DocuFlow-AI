"""
DocuFlow AI — Prometheus & OpenMetrics Instrumentation Engine.

Provides type-safe counters, gauges, and histograms with label support and standard
Prometheus text exposition format generation.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


def _extract_labels(label_names: tuple[str, ...], labels: dict[str, Any] | None, kwargs: dict[str, Any]) -> tuple[str, ...]:
    merged = {**(labels or {}), **kwargs}
    return tuple(str(merged.get(lbl, "")) for lbl in label_names)


def _format_metric_val(val: float) -> str:
    if val.is_integer():
        return str(int(val))
    return str(val)


class Counter:
    """Prometheus-compatible Counter metric."""

    def __init__(self, name: str, description: str, label_names: tuple[str, ...] | list[str] = ()) -> None:
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self._values: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, labels: dict[str, Any] | None = None, **kwargs: Any) -> None:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            self._values[key] += value

    def get(self, labels: dict[str, Any] | None = None, **kwargs: Any) -> float:
        return self.get_value(labels=labels, **kwargs)

    def get_value(self, labels: dict[str, Any] | None = None, **kwargs: Any) -> float:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            return self._values[key]

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            if not self._values and not self.label_names:
                lines.append(f"{self.name} 0")
            for key, val in self._values.items():
                if self.label_names:
                    label_str = ",".join(
                        f'{name}="{v}"' for name, v in zip(self.label_names, key, strict=False)
                    )
                    lines.append(f"{self.name}{{{label_str}}} {_format_metric_val(val)}")
                else:
                    lines.append(f"{self.name} {_format_metric_val(val)}")
        return lines


class Gauge:
    """Prometheus-compatible Gauge metric."""

    def __init__(self, name: str, description: str, label_names: tuple[str, ...] | list[str] = ()) -> None:
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self._values: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, labels: dict[str, Any] | None = None, **kwargs: Any) -> None:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, labels: dict[str, Any] | None = None, **kwargs: Any) -> None:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1.0, labels: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self.inc(-value, labels=labels, **kwargs)

    def get(self, labels: dict[str, Any] | None = None, **kwargs: Any) -> float:
        return self.get_value(labels=labels, **kwargs)

    def get_value(self, labels: dict[str, Any] | None = None, **kwargs: Any) -> float:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            return self._values[key]

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            if not self._values and not self.label_names:
                lines.append(f"{self.name} 0")
            for key, val in self._values.items():
                if self.label_names:
                    label_str = ",".join(
                        f'{name}="{v}"' for name, v in zip(self.label_names, key, strict=False)
                    )
                    lines.append(f"{self.name}{{{label_str}}} {_format_metric_val(val)}")
                else:
                    lines.append(f"{self.name} {_format_metric_val(val)}")
        return lines


class Histogram:
    """Prometheus-compatible Histogram metric."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str,
        label_names: tuple[str, ...] | list[str] = (),
        buckets: tuple[float, ...] | list[float] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self.buckets = tuple(sorted(buckets)) if buckets else self.DEFAULT_BUCKETS
        self._counts: dict[tuple[str, ...], int] = defaultdict(int)
        self._sums: dict[tuple[str, ...], float] = defaultdict(float)
        self._bucket_counts: dict[tuple[str, ...], dict[float, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._lock = threading.Lock()

    def observe(self, value: float, labels: dict[str, Any] | None = None, **kwargs: Any) -> None:
        key = _extract_labels(self.label_names, labels, kwargs)
        with self._lock:
            self._counts[key] += 1
            self._sums[key] += value
            for b in self.buckets:
                if value <= b:
                    self._bucket_counts[key][b] += 1

    def collect(self) -> list[dict[str, Any]]:
        results = []
        with self._lock:
            for key in self._counts:
                labels_dict = dict(zip(self.label_names, key, strict=False))
                bucket_data: dict[float, int] = {}
                for b in self.buckets:
                    bucket_data[b] = self._bucket_counts[key][b]
                bucket_data[float("inf")] = self._counts[key]
                results.append({
                    "labels": labels_dict,
                    "count": self._counts[key],
                    "sum": round(self._sums[key], 6),
                    "buckets": bucket_data,
                })
        return results

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for key in self._counts:
                labels_dict = dict(zip(self.label_names, key, strict=False))
                for b in self.buckets:
                    count_in_bucket = self._bucket_counts[key][b]
                    b_labels = {**labels_dict, "le": str(b)}
                    label_str = ",".join(f'{k}="{v}"' for k, v in b_labels.items())
                    lines.append(f"{self.name}_bucket{{{label_str}}} {count_in_bucket}")

                # +Inf bucket
                inf_labels = {**labels_dict, "le": "+Inf"}
                inf_str = ",".join(f'{k}="{v}"' for k, v in inf_labels.items())
                lines.append(f"{self.name}_bucket{{{inf_str}}} {self._counts[key]}")

                # Sum and count
                label_str = (
                    "," + ",".join(f'{k}="{v}"' for k, v in labels_dict.items())
                    if labels_dict
                    else ""
                )
                if label_str.startswith(","):
                    label_str = label_str[1:]
                if label_str:
                    lines.append(f"{self.name}_sum{{{label_str}}} {_format_metric_val(self._sums[key])}")
                    lines.append(f"{self.name}_count{{{label_str}}} {self._counts[key]}")
                else:
                    lines.append(f"{self.name}_sum {_format_metric_val(self._sums[key])}")
                    lines.append(f"{self.name}_count {self._counts[key]}")
        return lines


class MetricsRegistry:
    """Central registry maintaining all application metrics."""

    def __init__(self) -> None:
        self._init_metrics()

    def _init_metrics(self) -> None:
        # Standard HTTP Metrics
        self.http_requests_total = Counter(
            "docuflow_http_requests_total",
            "Total number of HTTP requests processed",
            label_names=["method", "endpoint", "status_code"],
        )
        self.http_request_duration_seconds = Histogram(
            "docuflow_http_request_duration_seconds",
            "HTTP request latency in seconds",
            label_names=["method", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        self.http_errors_total = Counter(
            "docuflow_http_errors_total",
            "Total number of HTTP 4xx/5xx errors",
            label_names=["method", "endpoint", "status_code", "error_type"],
        )

        # Document & Job Metrics
        self.document_uploads_total = Counter(
            "docuflow_document_uploads_total",
            "Total number of uploaded documents",
            label_names=["mime_type", "tenant_id"],
        )
        self.document_processing_total = Counter(
            "docuflow_document_processing_total",
            "Total number of document processing jobs initiated",
            label_names=["status"],
        )
        self.document_processing_failures_total = Counter(
            "docuflow_document_processing_failures_total",
            "Total number of document processing failures",
            label_names=["error_category"],
        )
        self.document_processing_duration_seconds = Histogram(
            "docuflow_document_processing_duration_seconds",
            "Document processing latency from queue to completion in seconds",
            label_names=["mime_type"],
            buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        )

        # Worker & Celery Queue Metrics
        self.celery_queue_depth = Gauge(
            "docuflow_celery_queue_depth",
            "Current depth of Celery parsing and indexing task queues",
            label_names=["queue_name"],
        )
        self.celery_task_failures_total = Counter(
            "docuflow_celery_task_failures_total",
            "Total number of Celery task execution failures",
            label_names=["task_name", "error_category"],
        )

        # Embedding & Qdrant Operations
        self.embedding_generation_duration_seconds = Histogram(
            "docuflow_embedding_generation_duration_seconds",
            "Time spent generating dense/sparse vector embeddings in seconds",
            label_names=["model_name"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )
        self.qdrant_operation_duration_seconds = Histogram(
            "docuflow_qdrant_operation_duration_seconds",
            "Latency of Qdrant vector database queries and upserts in seconds",
            label_names=["operation"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Storage Operations
        self.storage_operations_total = Counter(
            "docuflow_storage_operations_total",
            "Total object storage operations (put, get, delete)",
            label_names=["operation", "status"],
        )
        self.storage_failures_total = Counter(
            "docuflow_storage_failures_total",
            "Total storage operation failures",
            label_names=["operation"],
        )

    def generate_prometheus_exposition(self) -> str:
        """Render all registered metrics into Prometheus exposition text format."""
        all_metrics: list[Any] = [
            self.http_requests_total,
            self.http_request_duration_seconds,
            self.http_errors_total,
            self.document_uploads_total,
            self.document_processing_total,
            self.document_processing_failures_total,
            self.document_processing_duration_seconds,
            self.celery_queue_depth,
            self.celery_task_failures_total,
            self.embedding_generation_duration_seconds,
            self.qdrant_operation_duration_seconds,
            self.storage_operations_total,
            self.storage_failures_total,
        ]

        rendered_blocks: list[str] = []
        for metric in all_metrics:
            lines = metric.render()
            if lines:
                rendered_blocks.append("\n".join(lines))

        return "\n\n".join(rendered_blocks) + "\n"

    def generate_prometheus_output(self) -> str:
        """Render all metrics into Prometheus exposition text format (alias)."""
        return self.generate_prometheus_exposition()

    def reset(self) -> None:
        """Reset all metrics (useful for isolated unit tests)."""
        self._init_metrics()


_global_registry = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    """Return application global metrics singleton."""
    return _global_registry

