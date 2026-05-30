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
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Manage identifiers for the request lifecycle.

        Ensures request/correlation ids are validated, placed into contextvars for logging,
        and attached to every response (including error paths). This implementation
        maintains previous behavior: context set/reset, exception delegation, and header propagation.
        """
        import asyncio
        import inspect

        # Local imports to avoid circular dependency at module import time and to keep middleware
        # initialization lightweight. These are intentionally imported inside dispatch.
        from fastapi import HTTPException
        from fastapi.exception_handlers import http_exception_handler
        from fastapi.responses import JSONResponse

        # Prefer a module-provided validator but fall back to a conservative local one
        validator = globals().get("is_valid_id")
        if validator is None:

            def _local_is_valid_id(val: str | None) -> bool:
                if not val:
                    return False
                # Reject CR/LF to prevent header injection and ensure printable
                if "\r" in val or "\n" in val:
                    return False
                # Basic non-empty check; central validator should provide stricter rules.
                return True

            validator = _local_is_valid_id
        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if validator(raw_request_id) else str(uuid.uuid4())
        raw_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = raw_correlation_id if validator(raw_correlation_id) else request_id

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
            handler = next(
                (exception_handlers.get(cls) for cls in type(exc).__mro__ if exception_handlers.get(cls) is not None),
                http_exception_handler,
            )
            try:
                result = handler(request, exc)
                response = await result if inspect.isawaitable(result) else result
            except Exception:
                logger.exception(
                    "Exception while handling HTTPException",
                    extra={"request_id": request_id, "correlation_id": correlation_id},
                )
                response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        except Exception:
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
