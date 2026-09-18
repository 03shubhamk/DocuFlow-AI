"""
DocuFlow AI — OpenTelemetry-Compatible Distributed Tracing Engine.

Provides span management, W3C traceparent context propagation, and structured
telemetry across the ingestion and retrieval lifecycle:
API Request -> Celery Task -> Docling -> Normalizer -> Chunker -> Embedding -> Qdrant.
"""

from __future__ import annotations

import contextvars
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

import structlog

logger = structlog.get_logger(__name__)

# Context variable tracking current active span
_current_span_var: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "docuflow_current_span", default=None
)


def generate_trace_id() -> str:
    """Generate a 16-byte (32-character) hex OpenTelemetry-compliant trace ID."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate an 8-byte (16-character) hex OpenTelemetry-compliant span ID."""
    return secrets.token_hex(8)


@dataclass
class SpanContext:
    """W3C-compliant Trace Context."""

    trace_id: str
    span_id: str
    trace_flags: str = "01"  # Sampled
    parent_span_id: str | None = None

    @classmethod
    def from_traceparent(cls, header: str | None) -> SpanContext | None:
        """Parse standard W3C 'traceparent' header (e.g. '00-{trace_id}-{span_id}-01')."""
        if not header:
            return None
        parts = header.strip().split("-")
        if len(parts) == 4 and parts[0] == "00" and len(parts[1]) == 32 and len(parts[2]) == 16:
            return cls(trace_id=parts[1], span_id=parts[2], trace_flags=parts[3], parent_span_id=parts[2])
        return None

    def to_traceparent(self) -> str:
        """Format as standard W3C 'traceparent' header."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


@dataclass
class Span:
    """Represents a single timed unit of work in a distributed trace."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None
    status: str = "OK"  # "OK" | "ERROR"
    error_message: str | None = None

    @property
    def context(self) -> SpanContext:
        """Return the span context corresponding to this span."""
        return SpanContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
        )

    @property
    def duration_ms(self) -> float | None:
        """Return duration in milliseconds if ended."""
        if self.end_time is not None:
            return (self.end_time - self.start_time) * 1000
        return None

    def set_attribute(self, key: str, value: Any) -> Span:
        """Set a metadata attribute on the active span."""
        self.attributes[key] = value
        return self

    def set_attributes(self, attrs: dict[str, Any]) -> Span:
        """Set multiple metadata attributes on the active span."""
        self.attributes.update(attrs)
        return self

    def record_exception(self, exc: Exception) -> None:
        """Mark span as failed and attach exception message."""
        self.status = "ERROR"
        self.error_message = str(exc)
        self.attributes["error"] = True
        self.attributes["error.type"] = exc.__class__.__name__
        self.attributes["error.message"] = str(exc)

    def finish(self) -> float:
        """Complete the span and record execution duration in milliseconds."""
        self.end_time = time.perf_counter()
        dur_ms = (self.end_time - self.start_time) * 1000
        attrs = dict(self.attributes)
        attrs.pop("duration_ms", None)

        # Emit structured log for span completion
        logger.info(
            "trace_span_completed",
            span_name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            status=self.status,
            duration_ms=round(dur_ms, 2),
            **attrs,
        )
        return dur_ms


class DocuFlowTracer:
    """OpenTelemetry-compatible tracer instance."""

    def __init__(self, service_name: str = "docuflow-api") -> None:
        self.service_name = service_name

    def extract_traceparent(self, header: str | None) -> SpanContext | None:
        """Parse W3C traceparent header."""
        return SpanContext.from_traceparent(header)

    def format_traceparent(self, context: SpanContext) -> str:
        """Format W3C traceparent string."""
        return context.to_traceparent()

    @contextmanager
    def start_span(
        self,
        name: str,
        parent: SpanContext | None = None,
        parent_context: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Start a new span as a context manager."""
        effective_parent = parent or parent_context
        current_active = _current_span_var.get()

        if effective_parent:
            trace_id = effective_parent.trace_id
            parent_id = effective_parent.span_id
        elif current_active:
            trace_id = current_active.trace_id
            parent_id = current_active.span_id
        else:
            trace_id = generate_trace_id()
            parent_id = None

        span_id = generate_span_id()
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            attributes={
                "service.name": self.service_name,
                **(attributes or {}),
            },
        )

        token = _current_span_var.set(span)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.finish()
            _current_span_var.reset(token)

    def get_current_span(self) -> Span | None:
        """Return the active span from context."""
        return _current_span_var.get()


_global_tracer = DocuFlowTracer()


def get_tracer() -> DocuFlowTracer:
    """Return the global tracer instance."""
    return _global_tracer


def extract_traceparent(header: str | None) -> SpanContext | None:
    """Extract traceparent context."""
    return _global_tracer.extract_traceparent(header)


def format_traceparent(context: SpanContext) -> str:
    """Format traceparent header."""
    return _global_tracer.format_traceparent(context)


def start_span(
    name: str,
    parent: SpanContext | None = None,
    parent_context: SpanContext | None = None,
    attributes: dict[str, Any] | None = None,
):
    """Module-level context manager to start a span."""
    return _global_tracer.start_span(
        name=name,
        parent=parent,
        parent_context=parent_context,
        attributes=attributes,
    )


def get_current_span() -> Span | None:
    """Return the active span."""
    return _global_tracer.get_current_span()

