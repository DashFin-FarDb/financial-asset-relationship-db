"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders, State

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

        # Extract headers using Starlette helper (handles decoding and case normalization)
        headers = Headers(scope=scope)
        raw_request_id = headers.get("x-request-id")
        raw_correlation_id = headers.get("x-correlation-id")

        # Defensive trimming then validation. Accept slightly malformed values (trim whitespace)
        # but still reject injection attempts; log invalid headers for diagnostics.
        if isinstance(raw_request_id, str):
            raw_request_id = raw_request_id.strip()
            if not is_valid_id(raw_request_id):
                logger.debug("Invalid X-Request-ID header received: %r", raw_request_id)
                raw_request_id = None

        if isinstance(raw_correlation_id, str):
            raw_correlation_id = raw_correlation_id.strip()
            if not is_valid_id(raw_correlation_id):
                logger.debug("Invalid X-Correlation-ID header received: %r", raw_correlation_id)
                raw_correlation_id = None

        request_id = raw_request_id if raw_request_id is not None else str(uuid.uuid4())
        correlation_id = raw_correlation_id if raw_correlation_id is not None else request_id

        # Expose identifiers on request state (compatible with FastAPI Request.state)
        state_obj = scope.setdefault("state", State())
        if isinstance(state_obj, dict):
            state_obj["request_id"] = request_id
            state_obj["correlation_id"] = correlation_id
        else:
            setattr(state_obj, "request_id", request_id)
            setattr(state_obj, "correlation_id", correlation_id)

        async def send_with_correlation_headers(message: dict) -> None:
            """Wrapper for the send callable to inject correlation headers."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                # Set values (replace existing) to avoid duplicate headers
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Correlation-ID"] = correlation_id

            await send(message)

        tokens = None
        try:
            # Set contextvars for downstream code (including logging)
            tokens = set_request_context(request_id, correlation_id)
            await self.app(scope, receive, send_with_correlation_headers)
        finally:
            if tokens is not None:
                reset_request_context(tokens)
