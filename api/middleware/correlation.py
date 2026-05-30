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
    Reliability: Ensures identifiers are attached to responses for both successful and error outcomes.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Manage identifiers for the request lifecycle."""
        import asyncio as _asyncio

        from fastapi import HTTPException as _HTTPException
        from fastapi.exception_handlers import (
            http_exception_handler as _http_exc_handler,
        )

        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())

        raw_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        tokens = set_request_context(request_id, correlation_id)
        try:
            response = await call_next(request)
        except _asyncio.CancelledError:
            raise
        except _HTTPException as exc:
            response = await _http_exc_handler(request, exc)
        except Exception:
            import logging as _logging

            _logging.getLogger(__name__).exception(
                "Unhandled exception in request processing",
                extra={"request_id": request_id, "correlation_id": correlation_id},
            )
            from starlette.responses import Response as StarletteResponse

            response = StarletteResponse("Internal Server Error", status_code=500)
        finally:
            reset_request_context(tokens)

        self._attach_headers(response, request_id, correlation_id)
        return response

    def _attach_headers(
        self,
        response: Response,
        request_id: str,
        correlation_id: str,
    ) -> None:
        """Attach correlation headers to the response."""
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
