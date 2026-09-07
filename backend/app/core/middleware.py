"""Observability, correlation ID, and Prometheus metrics middleware for FastAPI."""

import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import (
    active_requests,
    http_request_duration_seconds,
    http_requests_total,
)

# UUID and common ID pattern matchers for fallback route normalization
UUID_REGEX = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
INSP_ID_REGEX = re.compile(r"(?:insp|img|batch|rule)_[0-9a-zA-Z_\-]+")
INT_ID_REGEX = re.compile(r"/\d+(?=/|$)")


def normalize_path(scope: Scope) -> str:
    """Normalize URL path using matched route format or fallback regex to avoid metric cardinality explosion."""
    # 1. Best: matched route path template from FastAPI scope
    route = scope.get("route")
    if route and hasattr(route, "path"):
        return route.path

    # 2. Fallback: sanitize path using regex
    path = scope.get("path", "")
    path = UUID_REGEX.sub("{id}", path)
    path = INSP_ID_REGEX.sub("{id}", path)
    path = INT_ID_REGEX.sub("/{id}", path)
    return path


class ObservabilityMiddleware:
    """ASGI-native request metrics middleware that preserves streaming upload bodies."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Correlation ID: reuse existing header or generate fresh UUID
        request_id = next(
            (value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"x-request-id"),
            None,
        )
        if not request_id:
            request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        # Skip metric tracking for internal /metrics endpoint to avoid self-referential scrape noise
        is_metrics_endpoint = scope.get("path") == "/metrics"

        if not is_metrics_endpoint:
            active_requests.inc()

        start_time = time.perf_counter()
        status_code = 500

        async def send_with_correlation(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(raw=message["headers"])
                response_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            duration = time.perf_counter() - start_time
            if not is_metrics_endpoint:
                active_requests.dec()
                endpoint = normalize_path(scope)
                method = scope.get("method", "UNKNOWN")

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
