"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

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

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Manage identifiers for the request lifecycle.

        Ensures request/correlation ids are validated, placed into contextvars for logging,
        and attached to every response (including error paths).
        """
        import asyncio
        import inspect

        # Local imports to avoid circular dependency at module import time.
        from fastapi import HTTPException
        from fastapi.exception_handlers import http_exception_handler
        from fastapi.responses import JSONResponse

        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())
        raw_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        # Expose identifiers on request.state for downstream handlers/tests
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        tokens = None
        response: Response | None = None
        try:
            # Set contextvars for downstream code
            tokens = set_request_context(request_id, correlation_id)
            response = await call_next(request)
        except asyncio.CancelledError:
            # Allow cancellations to propagate
            raise
        except HTTPException as exc:
            # Delegate to configured exception handlers (if any), falling back to FastAPI's handler
            exception_handlers = getattr(getattr(request, "app", None), "exception_handlers", {})
            handler = http_exception_handler
            for cls in type(exc).__mro__:
                if cls in exception_handlers:
                    handler = exception_handlers[cls]
                    break
            try:
                result = handler(request, exc)
            except Exception:
                logger.exception(
                    "Exception while handling HTTPException",
                    extra={"request_id": request_id, "correlation_id": correlation_id},
                )
                response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        except Exception:
            # If in debug mode, re-raise to allow FastAPI's default debug page to render
            if getattr(request.app, "debug", False):
                raise

            logger.exception(
                "Unhandled exception in request processing",
                extra={"request_id": request_id, "correlation_id": correlation_id},
            )
            response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        finally:
            if tokens is not None:
                reset_request_context(tokens)
            if response is None:
                response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)

            # Attach headers after the handler has run so they are applied to both
            # success and error responses. Note: headers cannot be modified for
            # StreamingResponse after the first chunk is yielded.
            try:
                self._attach_headers(response, request_id, correlation_id)
            except Exception:
                logger.exception(
                    "Failed to attach correlation headers to response",
                    extra={"request_id": request_id, "correlation_id": correlation_id},
                )
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
