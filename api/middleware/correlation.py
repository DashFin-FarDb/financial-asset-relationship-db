"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from api.observability.context import is_valid_id, reset_request_context, set_request_context

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

    Security: Validates incoming IDs to prevent log/header injection.
    Reliability: Ensures IDs are attached to responses even on unhandled errors.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Manage identifiers for the request lifecycle.
        """
        # Extract and validate headers
        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())

        raw_correlation_id = request.headers.get("X-Correlation-ID")
        # If correlation ID is invalid or missing, default to the (validated or generated) request_id
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        # Store identifiers in request state
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        # Set context variables
        tokens = set_request_context(request_id, correlation_id)

        try:
            response = await call_next(request)
            self._attach_headers(response, request_id, correlation_id)
            return response
        except Exception:
            # Re-raise will be caught by FastAPI exception handlers,
            # but standard middleware might not have another chance to attach headers
            # if the exception handler returns a new response.
            # BaseHTTPMiddleware's call_next handles internal exceptions,
            # but if we get here, something went wrong in the middleware chain.
            raise
        finally:
            # Clear context variables
            reset_request_context(tokens)

    def _attach_headers(self, response: Response, request_id: str, correlation_id: str) -> None:
        """Attach correlation headers to the response."""
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
