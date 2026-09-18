"""
DocuFlow AI — Unit Tests for Observability Architecture.

Tests metric collection, Prometheus exposition format, and OpenTelemetry tracer functionality.
"""

from __future__ import annotations

import time

from app.infrastructure.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)
from app.infrastructure.observability.tracer import DocuFlowTracer, SpanContext


class TestMetrics:
    def test_counter_increments_and_labels(self):
        c = Counter("test_counter", "Test counter description", label_names=("method", "status"))
        c.inc()
        c.inc(value=2.5)
        c.inc(labels={"method": "GET", "status": "200"})

        assert c.get() == 3.5
        assert c.get(labels={"method": "GET", "status": "200"}) == 1.0

    def test_gauge_set_inc_dec(self):
        g = Gauge("test_gauge", "Test gauge description")
        g.set(10.0)
        assert g.get() == 10.0
        g.inc(5.0)
        assert g.get() == 15.0
        g.dec(3.0)
        assert g.get() == 12.0

    def test_histogram_observations_and_buckets(self):
        h = Histogram(
            "test_histogram",
            "Test histogram description",
            buckets=(0.1, 0.5, 1.0),
        )
        h.observe(0.05)
        h.observe(0.3)
        h.observe(0.8)
        h.observe(2.0)

        data = h.collect()
        # Find default label entry
        entry = next(d for d in data if d["labels"] == {})
        assert entry["count"] == 4
        assert entry["sum"] == round(0.05 + 0.3 + 0.8 + 2.0, 6)
        assert entry["buckets"][0.1] == 1
        assert entry["buckets"][0.5] == 2
        assert entry["buckets"][1.0] == 3
        assert entry["buckets"][float("inf")] == 4

    def test_metrics_registry_prometheus_output(self):
        reg = MetricsRegistry()
        reg.http_requests_total.inc(labels={"method": "POST", "endpoint": "/api/v1/documents", "status_code": "201"})
        reg.celery_queue_depth.set(3, labels={"queue_name": "parsing"})

        output = reg.generate_prometheus_output()
        assert "# HELP docuflow_http_requests_total" in output
        assert "# TYPE docuflow_http_requests_total counter" in output
        assert 'docuflow_http_requests_total{method="POST",endpoint="/api/v1/documents",status_code="201"} 1' in output
        assert "# TYPE docuflow_celery_queue_depth gauge" in output
        assert 'docuflow_celery_queue_depth{queue_name="parsing"} 3' in output



class TestTracer:
    def test_traceparent_format_and_extraction(self):
        tracer = DocuFlowTracer()
        ctx = SpanContext(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            trace_flags="01",
        )
        formatted = tracer.format_traceparent(ctx)
        assert formatted == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        extracted = tracer.extract_traceparent(formatted)
        assert extracted is not None
        assert extracted.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert extracted.parent_span_id == "00f067aa0ba902b7"
        assert extracted.trace_flags == "01"

    def test_invalid_traceparent_returns_none(self):
        tracer = DocuFlowTracer()
        assert tracer.extract_traceparent("invalid-traceparent") is None
        assert tracer.extract_traceparent("") is None

    def test_span_lifecycle_and_nesting(self):
        tracer = DocuFlowTracer()

        with tracer.start_span("root_span") as root:
            root.set_attribute("env", "test")
            assert tracer.get_current_span() is root

            with tracer.start_span("child_span") as child:
                assert tracer.get_current_span() is child
                assert child.context.trace_id == root.context.trace_id
                assert child.context.parent_span_id == root.context.span_id
                time.sleep(0.01)

            assert tracer.get_current_span() is root
            assert child.end_time is not None
            assert child.duration_ms is not None and child.duration_ms > 0

        assert tracer.get_current_span() is None
        assert root.end_time is not None
        assert root.duration_ms is not None and root.duration_ms > 0

    def test_span_exception_recording(self):
        tracer = DocuFlowTracer()
        span_ref = None

        try:
            with tracer.start_span("failing_span") as span:
                span_ref = span
                raise ValueError("Simulated failure")
        except ValueError:
            pass

        assert span_ref is not None
        assert span_ref.attributes.get("error") is True
        assert "Simulated failure" in span_ref.attributes.get("error.message", "")
