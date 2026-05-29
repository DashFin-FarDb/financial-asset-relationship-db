"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from api.observability.context import reset_request_context, set_request_context

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.middleware.base import RequestResponseEndpoint


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that manages request and correlation identifiers.

    This middleware manages two semantically distinct identifiers:
    - request_id: Scoped to a single HTTP request. Extracted from X-Request-ID
      header or generated as UUID4 if absent.
    - correlation_id: Cross-service/cross-job workflow identity. Extracted from
      X-Correlation-ID header or defaults to the request_id value for
      request-initiated workflows.

    The distinction is crucial for observability:
    - Use request_id for tracing a single request's execution path.
    - Use correlation_id for tracing an entire workflow that might span multiple
      requests or involve background jobs (e.g., an async graph rebuild operation
      triggered by a specific user request).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Manage identifiers for the request lifecycle.

        1. Extract or generate identifiers.
        2. Store them in request state.
        3. Set them in request context (contextvars).
        4. Propagate them to response headers.
        5. Ensure context cleanup.
        """
        # Extract or generate identifiers
        # X-Request-ID is for this specific request
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # X-Correlation-ID is for the broader workflow
        # If not provided, it defaults to the request_id (starting a new workflow)
        correlation_id = request.headers.get("X-Correlation-ID") or request_id

        # Store identifiers in request state for easy access via request object
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        # Set context variables for access throughout the request lifecycle
        # (including deep within business logic without explicit passing)
        tokens = set_request_context(request_id, correlation_id)

        try:
            response = await call_next(request)

            # Propagate identifiers to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id

            return response
        finally:
            # Clear context variables at request boundaries to prevent leakage
            reset_request_context(tokens)
