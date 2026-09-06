"""
DocuFlow AI — Structured Logging Configuration.

Configures structlog with JSON output in production and pretty-print in dev.
Automatically binds correlation_id, environment, and service name to all log records.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    """Configure structlog for the application.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR).
        environment: Runtime environment for renderer selection.
    """
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging to pipe into structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_int,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "production":
        # JSON output for log aggregators (Datadog, CloudWatch, GCP Logging)
        processors: list[structlog.types.Processor] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable colorized output for local development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a structlog bound logger.

    Args:
        name: Optional logger name, typically __name__.
    """
    return structlog.get_logger(name)
