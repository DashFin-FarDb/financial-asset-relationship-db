"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.middleware.base import RequestResponseEndpoint

from api.observability.context import is_valid_id, reset_request_context, set_request_context


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
        tokens = None
        try:
            tokens = set_request_context(request_id, correlation_id)
            response = await call_next(request)
        except Exception as exc:
            # Propagate task cancellation immediately so cancel flows aren't swallowed
            import asyncio as _asyncio

            if isinstance(exc, _asyncio.CancelledError):
                raise
            # Re-raise FastAPI HTTPException so framework handlers run
            try:
                from fastapi import HTTPException as _HTTPException
            except Exception:
                _HTTPException = None
            if _HTTPException is not None and isinstance(exc, _HTTPException):
                raise
            # Log unexpected errors and return generic 500 (do not expose internals)
            import logging as _logging

            _logging.getLogger(__name__).exception("Unhandled exception in request processing")
            from starlette.responses import Response as StarletteResponse

            response = StarletteResponse("Internal Server Error", status_code=500)
        finally:
            # Clear context variables
            if tokens is not None:
                reset_request_context(tokens)
        self._attach_headers(response, request_id, correlation_id)
        return response

    def _attach_headers(self, response: Response, request_id: str, correlation_id: str) -> None:
        """Attach correlation headers to the response."""
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
