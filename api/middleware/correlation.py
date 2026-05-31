"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders, State

from api.observability.context import is_valid_id, reset_request_context, set_request_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


MAX_HEADER_LENGTH = 1024
LOG_TRUNCATE_LEN = 200


def _extract_and_validate_id(raw_id: str | None, header_name: str) -> str | None:
    """Extract, trim, and validate an ID from a header safely."""
    if not isinstance(raw_id, str):
        return None

    log_len = len(raw_id)
    # Reject extremely large headers before trimming to prevent memory exhaustion DoS
    if log_len > MAX_HEADER_LENGTH:
        logger.debug("Oversized %s header received (redacted), length=%d", header_name, log_len)
        return None

    trimmed_id = raw_id.strip()
    trimmed_len = len(trimmed_id)
    if not is_valid_id(trimmed_id):
        logger.debug(
            "Invalid %s header received (redacted), trimmed_length=%d",
            header_name,
            min(trimmed_len, LOG_TRUNCATE_LEN),
        )
        return None

    return trimmed_id


def _inject_state(scope: Scope, request_id: str, correlation_id: str) -> None:
    """Expose identifiers on request state (compatible with FastAPI Request.state)."""
    state_obj = scope.get("state")
    if state_obj is None:
        state_obj = State()
        scope["state"] = state_obj

    # We prefer mapping assignment first for compatibility with dict-like test seams
    # and pure ASGI scope dictionaries, falling back to attribute-style assignment.
    if isinstance(state_obj, MutableMapping):
    if isinstance(state_obj, MutableMapping):
        try:
            state_obj["request_id"] = request_id
            state_obj["correlation_id"] = correlation_id
        except (TypeError, AttributeError) as assign_exc:
            # Mapping-style assignment failed; fall back to attribute assignment
            try:
                setattr(state_obj, "request_id", request_id)
                setattr(state_obj, "correlation_id", correlation_id)
            except (TypeError, AttributeError):
                logger.warning(
                    "Could not attach correlation IDs to state object of type %s (%s); continuing without state injection",
                    type(state_obj).__name__,
                    type(assign_exc).__name__,
                )
            except Exception as exc:
                # Unexpected error during attribute assignment; log at debug level with traceback for diagnostics
                logger.debug(
                    "Unexpected error while falling back to attribute assignment for state object %s: %s",
                    type(state_obj).__name__,
                    type(exc).__name__,
                    exc_info=True,
                )
        except Exception as exc:
            # Unexpected error while assigning into mapping; log at debug to avoid noisy traceback for non-fatal state injection errors.
            logger.debug(
                "Unexpected error while assigning into mapping-style state object %s: %s",
                type(state_obj).__name__,
                type(exc).__name__,
                exc_info=True,
            )
    else:
        try:
            setattr(state_obj, "request_id", request_id)
            setattr(state_obj, "correlation_id", correlation_id)
        except (TypeError, AttributeError) as exc:
            logger.warning(
                "Could not attach correlation IDs to state object of type %s (%s); continuing without state injection",
                type(state_obj).__name__,
                type(exc).__name__,
            )
            setattr(state_obj, "correlation_id", correlation_id)
        except (TypeError, AttributeError) as exc:
            logger.warning(
                "Could not attach correlation IDs to state object of type %s (%s); continuing without state injection",
                type(state_obj).__name__,
                type(exc).__name__,
            )


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
        raw_request_id = _extract_and_validate_id(headers.get("x-request-id"), "X-Request-ID")
        raw_correlation_id = _extract_and_validate_id(headers.get("x-correlation-id"), "X-Correlation-ID")

        request_id = raw_request_id if raw_request_id is not None else str(uuid.uuid4())
        correlation_id = raw_correlation_id if raw_correlation_id is not None else request_id

        _inject_state(scope, request_id, correlation_id)

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
