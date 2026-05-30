"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import uuid
import logging
import logging
import uuid
from __future__ import annotations
# (keep all imports at top; remove deferred 'import logging' inside except blocks)
logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
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
        # Deferred local imports to avoid circular imports and heavy FastAPI initialization at import time
        import asyncio
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
        from fastapi.exception_handlers import http_exception_handler

        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())

        raw_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        # Store identifiers in request state
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        tokens = None
        try:
            tokens = set_request_context(request_id, correlation_id)
            response = await call_next(request)
        except asyncio.CancelledError:
            raise
        except HTTPException as exc:
            raise
        except HTTPException as exc:
            import inspect

            exception_handlers = getattr(getattr(request, "app", None), "exception_handlers", {})
            handler = next(
                (
                    exception_handlers[cls]
                    for cls in type(exc).__mro__
                    if cls in exception_handlers
                ),
                http_exception_handler,
            )

            try:
                result = handler(request, exc)
                if inspect.isawaitable(result):
                    response = await result
                else:
                    response = result
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "Exception while handling HTTPException",
                    extra={"request_id": request_id, "correlation_id": correlation_id},
                )
                from fastapi.responses import JSONResponse

                response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        except Exception:
tokens = set_request_context(request_id, correlation_id)
try:
    response = await call_next(request)
except asyncio.CancelledError:
    raise
except HTTPException as exc:
    exception_handlers = getattr(getattr(request, 'app', None), 'exception_handlers', {})
    handler = next(
        (
            exception_handlers[cls]
            for cls in type(exc).__mro__
            if cls in exception_handlers
        ),
        http_exception_handler,
    )
    import inspect
    try:
        result = handler(request, exc)
        if inspect.isawaitable(result):
            response = await result
        else:
            response = result
    except Exception:
        logger.exception(
            'Exception while handling HTTPException',
            extra={'request_id': request_id, 'correlation_id': correlation_id},
        )
        response = JSONResponse({'detail': 'Internal Server Error'}, status_code=500)
except Exception:
    logger.exception(
        'Unhandled exception in request processing',
        extra={'request_id': request_id, 'correlation_id': correlation_id},
    )
    response = JSONResponse({'detail': 'Internal Server Error'}, status_code=500)
finally:
    reset_request_context(tokens)
    self._attach_headers(response, request_id, correlation_id)
return response

            logger.exception("Unhandled exception in request processing", extra={"request_id": request_id, "correlation_id": correlation_id})
response: Response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
tokens = set_request_context(request_id, correlation_id)
try:
    response = await call_next(request)
    ...

            response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Manage identifiers for the request lifecycle."""
        import asyncio
        import inspect
        from fastapi import HTTPException
        from fastapi.exception_handlers import http_exception_handler
        from fastapi.responses import JSONResponse

        raw_request_id = request.headers.get("X-Request-ID")
        request_id = raw_request_id if is_valid_id(raw_request_id) else str(uuid.uuid4())

        raw_correlation_id = request.headers.get("X-Correlation-ID")
        correlation_id = raw_correlation_id if is_valid_id(raw_correlation_id) else request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        tokens = set_request_context(request_id, correlation_id)
        response: Response
        try:
            response = await call_next(request)
        except asyncio.CancelledError:
            raise
        except HTTPException as exc:
            exception_handlers = getattr(getattr(request, "app", None), "exception_handlers", {})
            handler = next(
                (exception_handlers[cls] for cls in type(exc).__mro__ if cls in exception_handlers),
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
            reset_request_context(tokens)
            self._attach_headers(response, request_id, correlation_id)
        return response
            if tokens is not None:
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
