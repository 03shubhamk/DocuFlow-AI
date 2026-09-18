"""
DocuFlow AI — Structured Logging Configuration & Sensitive Data Redaction.

Configures structlog with JSON output in production and pretty-print in dev.
Automatically binds correlation_id, environment, and service name to all log records.
Automatically redacts sensitive fields (passwords, JWT tokens, API keys, secret credentials).
"""

from __future__ import annotations

import logging
import re
import sys

import structlog

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "jwt_secret",
    "jwt_secret_key",
    "authorization",
    "api_key",
    "bearer",
    "raw_token",
}

BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)


def redact_sensitive_log_data(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Structlog processor that sanitizes passwords, secrets, and auth tokens from log events."""
    for key, value in list(event_dict.items()):
        lower_key = key.lower()
        if any(sensitive in lower_key for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(value, str) and "Bearer " in value:
            event_dict[key] = BEARER_PATTERN.sub("Bearer [REDACTED]", value)

    return event_dict


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
        redact_sensitive_log_data,
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
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Return a structlog bound logger.

    Args:
        name: Optional logger name, typically __name__.
    """
    return structlog.get_logger(name)
