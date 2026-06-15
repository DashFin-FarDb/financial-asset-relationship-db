from __future__ import annotations

"""Example FastAPI ASGI middleware that demonstrates how to use the async_request_context
and async_trace_context context managers from src.observability.context.

This is a small, self-contained example intended for documentation and onboarding purposes only.
Use the same pattern in your production middleware to ensure request and trace context are
set and reset reliably across async boundaries.
"""

from typing import Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.observability.context import (
    async_request_context,
    async_trace_context,
)


class TracingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that extracts tracing headers and installs request/trace context.

    Expected headers (optional):
    - x-request-id
    - x-correlation-id
    - x-trace-id
    - x-span-id

    If request_id or correlation_id are missing, this middleware generates a stable
    request identifier (UUID4 hex). Trace/span IDs are accepted as-is when valid; the
    context helpers will validate them against the configured regex and drop invalid
    values.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        headers = request.headers
        request_id = headers.get("x-request-id") or f"req-{uuid4().hex}"
        correlation_id = headers.get("x-correlation-id") or f"corr-{uuid4().hex}"

        trace_id = headers.get("x-trace-id")
        span_id = headers.get("x-span-id")

        # Use async context managers to ensure set/reset semantics even across awaits
        async with async_request_context(request_id, correlation_id):
            async with async_trace_context(trace_id, span_id):
                response = await call_next(request)
        return response
