"""Observability, correlation ID, and Prometheus metrics middleware for FastAPI."""

import re
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import (
    active_requests,
    http_request_duration_seconds,
    http_requests_total,
)

# UUID and common ID pattern matchers for fallback route normalization
UUID_REGEX = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
INSP_ID_REGEX = re.compile(r"(?:insp|img|batch|rule)_[0-9a-zA-Z_\-]+")
INT_ID_REGEX = re.compile(r"/\d+(?=/|$)")


def normalize_path(request: Request) -> str:
    """Normalize URL path using matched route format or fallback regex to avoid metric cardinality explosion."""
    # 1. Best: matched route path template from FastAPI scope
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path

    # 2. Fallback: sanitize path using regex
    path = request.url.path
    path = UUID_REGEX.sub("{id}", path)
    path = INSP_ID_REGEX.sub("{id}", path)
    path = INT_ID_REGEX.sub("/{id}", path)
    return path


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request correlation ID tracing and Prometheus metric recording."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Correlation ID: reuse existing header or generate fresh UUID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Attach request_id to request state for downstream handlers and logging
        request.state.request_id = request_id

        # Skip metric tracking for internal /metrics endpoint to avoid self-referential scrape noise
        is_metrics_endpoint = request.url.path == "/metrics"

        if not is_metrics_endpoint:
            active_requests.inc()

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            if not is_metrics_endpoint:
                active_requests.dec()
                endpoint = normalize_path(request)
                method = request.method

                # Record Prometheus metrics safely
                try:
                    http_requests_total.labels(
                        method=method,
                        endpoint=endpoint,
                        status_code=str(status_code),
                    ).inc()

                    http_request_duration_seconds.labels(
                        method=method,
                        endpoint=endpoint,
                    ).observe(duration)
                except Exception:
                    pass

        # Inject correlation ID in response headers
        response.headers["X-Request-ID"] = request_id
        return response
