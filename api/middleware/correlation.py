"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders

from api.observability.context import is_valid_id, reset_request_context, set_request_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class CorrelationMiddleware:
    """
    Middleware that manages request and correlation identifiers.

    This middleware manages two semantically distinct identifiers:
    - request_id: Scoped to a single HTTP request. Extracted from X-Request-ID
      header or generated as UUID4 if absent.
    - correlation_id: Cross-service/cross-job workflow identity. Extracted from
      X-Correlation-ID header or defaults to the request_id value for
      request-initiated workflows.

    This is implemented as a plain ASGI middleware to avoid the overhead and
    edge-cases of BaseHTTPMiddleware (e.g., issues with StreamingResponse and
    background task cancellation).

    Security: Validates incoming IDs to prevent log/header injection.
    Reliability: Ensures identifiers are attached to responses for both successful and error outcomes.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Manage identifiers for the request lifecycle."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract headers from ASGI scope
        headers = dict(scope.get("headers", []))

        # Helper to get header by name (case-insensitive in ASGI)
        def get_header(name: str) -> str | None:
            name_bytes = name.lower().encode("latin-1")
            val = headers.get(name_bytes)
            return val.decode("latin-1") if val else None

        raw_request_id = get_header("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())

        raw_correlation_id = get_header("X-Correlation-ID")
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        # Expose identifiers on request state (compatible with FastAPI Request.state)
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id
        scope["state"]["correlation_id"] = correlation_id

        async def send_with_correlation_headers(message: dict) -> None:
            """Wrapper for the send callable to inject correlation headers."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers.append("X-Request-ID", request_id)
                response_headers.append("X-Correlation-ID", correlation_id)

            await send(message)

        tokens = None
        try:
            # Set contextvars for downstream code (including logging)
            tokens = set_request_context(request_id, correlation_id)
            await self.app(scope, receive, send_with_correlation_headers)
        finally:
            if tokens is not None:
                reset_request_context(tokens)
