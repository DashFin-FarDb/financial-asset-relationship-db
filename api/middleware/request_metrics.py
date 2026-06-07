"""Middleware for collecting HTTP request metrics."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from starlette.routing import Match

from api.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestMetricsMiddleware:
    """
    ASGI middleware for collecting Prometheus metrics on HTTP requests.

    This middleware records request latency (duration in seconds) and count,
    grouped by request method, resolved route template (to avoid high cardinality),
    and status code groups (e.g. 2xx, 5xx).

    It is implemented as a direct ASGI middleware to avoid the overhead of
    BaseHTTPMiddleware and prevent issues with StreamingResponse/task cancellation.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the request metrics middleware."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Record metrics for HTTP requests."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Exclude internal /api/metrics from metrics to prevent latency poll pollution
        if path == "/api/metrics":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        start_time = time.perf_counter()

        status_code = [200]  # default fallback if RESPONSE_START is not encountered

        async def send_wrapper(message: dict[str, Any]) -> None:
            """Wrap ASGI send to capture response status code."""
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time

            # Resolve the route template dynamically from application routes to keep cardinality low
            route_template = "unknown"
            app = scope.get("app")
            if app is not None and hasattr(app, "routes"):
                for r in app.routes:
                    match, _ = r.matches(scope)
                    if match == Match.FULL:
                        route_template = r.path
                        break

            status_group = f"{status_code[0] // 100}xx"

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                route=route_template,
                status_group=status_group,
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                route=route_template,
                status_group=status_group,
            ).observe(duration)
