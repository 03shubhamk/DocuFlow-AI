"""
DocuFlow AI — Production Security & Rate Limiting Middleware.

Implements:
1. OWASP Security Headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
2. Token Bucket / Sliding Window Rate Limiting (per Client IP and User Token)
3. Maximum Request Payload Body Size Enforcement (DDoS / Memory Exhaustion Protection)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects hardened OWASP security headers into every HTTP response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # OWASP Core Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy (allows API and Swagger documentation safely)
        if "/docs" in request.url.path or "/redoc" in request.url.path or "/openapi.json" in request.url.path:
            # Relaxed CSP for API interactive docs
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self';"
            )

        return response


class RateLimiter:
    """Sliding-window token bucket rate limiter tracking requests by client key."""

    def __init__(self, requests_per_minute: int = 120, burst: int = 30) -> None:
        self.default_requests_per_minute = requests_per_minute
        self.default_burst = burst
        self.rate = requests_per_minute / 60.0  # Tokens added per second
        self.capacity = float(requests_per_minute + burst)
        self.tokens: dict[str, float] = defaultdict(lambda: self.capacity)
        self.last_updated: dict[str, float] = defaultdict(time.perf_counter)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is permitted under rate limit for key.

        Returns:
            Tuple of (is_allowed, retry_after_seconds).
        """
        now = time.perf_counter()
        elapsed = now - self.last_updated[key]
        self.last_updated[key] = now

        # Add newly replenished tokens based on elapsed time
        self.tokens[key] = min(self.capacity, self.tokens[key] + elapsed * self.rate)

        if self.tokens[key] >= 1.0:
            self.tokens[key] -= 1.0
            return True, 0

        # Calculate time until 1 token is available
        missing_tokens = 1.0 - self.tokens[key]
        retry_after = max(1, int(missing_tokens / self.rate))
        return False, retry_after

    def reset(self) -> None:
        """Reset rate limiter state and restore baseline rate/capacity."""
        self.rate = self.default_requests_per_minute / 60.0
        self.capacity = float(self.default_requests_per_minute + self.default_burst)
        self.tokens.clear()
        self.last_updated.clear()


# Global rate limiter instance
_global_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_rate_limiter


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Enforces rate limits on all incoming requests by IP or Bearer token."""

    def __init__(self, app, rate_limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.limiter = rate_limiter or _global_rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.settings.rate_limit_enabled:
            return await call_next(request)

        # Bypass rate limits for health and docs endpoints
        path = request.url.path
        if path.startswith(("/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        # Identify client key via Authorization header or Client IP
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            client_key = f"auth:{auth_header[:32]}"
        else:
            client_ip = request.client.host if request.client else "unknown_ip"
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            client_key = f"ip:{client_ip}"

        allowed, retry_after = self.limiter.is_allowed(client_key)
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                client_key=client_key,
                path=path,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://docuflow.ai/errors/rate-limit-exceeded",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"Rate limit exceeded. Please retry after {retry_after} seconds.",
                    "instance": path,
                    "retry_after": retry_after,
                },
                headers={
                    "Content-Type": "application/problem+json",
                    "Retry-After": str(retry_after),
                },
            )

        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Enforces maximum payload size limits to protect against DoS memory attacks."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                path = request.url.path

                # Check route-specific limit
                if "/documents" in path and request.method == "POST":
                    limit = self.settings.max_request_body_size_bytes
                else:
                    limit = self.settings.max_json_body_size_bytes

                if content_length > limit:
                    logger.warning(
                        "payload_too_large",
                        content_length=content_length,
                        max_limit=limit,
                        path=path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "https://docuflow.ai/errors/payload-too-large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request body size {content_length} bytes exceeds maximum allowed limit of {limit} bytes.",
                            "instance": path,
                        },
                        headers={"Content-Type": "application/problem+json"},
                    )
            except ValueError:
                pass

        return await call_next(request)
