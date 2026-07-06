"""Middleware for collecting HTTP request metrics."""

from __future__ import annotations

import logging
import time
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

from api.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_IN_FLIGHT, HTTP_REQUESTS_TOTAL
from src.observability.facade import ObservabilityEvent, log_event

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}


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
        # Exclude internal /api/metrics (and trailing slash variants) from metrics to prevent latency poll pollution
        normalized_path = path.rstrip("/") if path != "/" else path
        if normalized_path == "/api/metrics":
            await self.app(scope, receive, send)
            return

        HTTP_REQUESTS_IN_FLIGHT.inc()
        method = scope.get("method", "GET").upper()
        if method not in ALLOWED_METHODS:
            method = "OTHER"
        start_time = time.perf_counter()

        status_code = 500

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            """Wrap ASGI send to capture response status code."""
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            status_code = 500
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="request_execution_failed",
                    message=f"Request failed with unhandled exception: {type(exc).__name__}",
                    metadata={"error": type(exc).__name__},
                ),
            )
            raise
        finally:
            HTTP_REQUESTS_IN_FLIGHT.dec()
            duration = time.perf_counter() - start_time

            # Resolve the route template dynamically from scope to keep cardinality low
            route_template = "unknown"

            # Check if Starlette route object is available in scope after routing
            route = scope.get("route")
            if route is not None and hasattr(route, "path"):
                route_template = route.path

            status_group = f"{status_code // 100}xx"

            try:
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
            except Exception as metric_exc:
                # Prevent metrics collection failure from masking the actual application result or exception
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="metrics_recording_failed",
                        message=f"Failed to record HTTP request metrics: {type(metric_exc).__name__}",
                        metadata={"error": type(metric_exc).__name__},
                    ),
                )
