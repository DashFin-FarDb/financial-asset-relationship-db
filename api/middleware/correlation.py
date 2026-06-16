"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

from starlette.datastructures import Headers, MutableHeaders

from src.observability.context import (
    is_valid_id,
    reset_request_context,
    reset_trace_context,
    set_request_context,
    set_trace_context,
)
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


MAX_HEADER_LENGTH = 1024
LOG_TRUNCATE_LEN = 200


def _extract_and_validate_id(raw_id: str | None, header_name: str) -> str | None:
    """
    Return a trimmed, validated identifier extracted from a header or None if the value is unacceptable.

    If `raw_id` is not a string the function returns `None`. If the original (pre-trim) length exceeds
    `MAX_HEADER_LENGTH` the header is rejected and a `correlation_id_oversized_header` observability event
    is emitted. The header value is trimmed and validated; if validation fails a
    `correlation_id_invalid_header` observability event is emitted.

    Parameters:
        raw_id (str | None): The raw header value to validate.
        header_name (str): The HTTP header name used in observability event metadata and messages.

    Returns:
        str | None: The trimmed identifier when valid, otherwise `None`.
    """
    if not isinstance(raw_id, str):
        return None

    log_len = len(raw_id)
    # Reject extremely large headers before trimming to prevent memory exhaustion DoS
    if log_len > MAX_HEADER_LENGTH:
        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="correlation_id_oversized_header",
                message=f"Oversized {header_name} header received (redacted), length={log_len}",
                metadata={"header_name": header_name, "length": log_len},
            ),
        )
        return None

    trimmed_id = raw_id.strip()
    trimmed_len = len(trimmed_id)
    if not is_valid_id(trimmed_id):
        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="correlation_id_invalid_header",
                message=(
                    f"Invalid {header_name} header received (redacted), "
                    f"trimmed_length={min(trimmed_len, LOG_TRUNCATE_LEN)}"
                ),
                metadata={"header_name": header_name, "trimmed_length": trimmed_len},
            ),
        )
        return None

    return trimmed_id


def _inject_state(scope: Scope, request_id: str, correlation_id: str, trace_id: str, span_id: str) -> None:
    """
    Best-effort attach identifiers to the ASGI scope's state.

    This associates the given request and correlation identifiers into the ASGI scope's state for downstream
    handlers.

    Attempts to write identifiers into scope["state"] using either mapping-style or attribute-style
    assignment; failures are logged via observability events and do not raise exceptions.

    Parameters:
        scope (Scope): The ASGI connection scope whose "state" may be modified.
        request_id (str): Request identifier to attach to the state.
        correlation_id (str): Correlation identifier to attach to the state.
        trace_id (str): Trace identifier to attach to the state.
        span_id (str): Span identifier to attach to the state.
    """
    state_obj = scope.get("state")
    if state_obj is None:
        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="correlation_id_state_injection_skipped_no_state",
                message="No state object in scope; skipping correlation state injection",
            ),
        )
        return

    is_mapping = isinstance(state_obj, MutableMapping)

    for key, value in [
        ("request_id", request_id),
        ("correlation_id", correlation_id),
        ("trace_id", trace_id),
        ("span_id", span_id),
    ]:
        try:
            if is_mapping:
                try:
                    state_obj[key] = value
                    continue
                except (TypeError, AttributeError):
                    pass
            setattr(state_obj, key, value)
        except (TypeError, AttributeError) as exc:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="correlation_id_state_injection_failed",
                    message=(
                        f"Could not attach correlation IDs to state object of type {type(state_obj).__name__} "
                        f"({type(exc).__name__}); continuing without state injection"
                    ),
                    metadata={"state_type": type(state_obj).__name__, "error": type(exc).__name__},
                ),
            )
            continue
        except Exception as exc:
            log_event(
                logger,
                logging.DEBUG,
                ObservabilityEvent(
                    event="correlation_id_state_injection_error",
                    message=(
                        f"Unexpected error while attaching correlation IDs to state "
                        f"object {type(state_obj).__name__}: {type(exc).__name__}"
                    ),
                    metadata={"state_type": type(state_obj).__name__, "error": type(exc).__name__},
                ),
            )
            continue


class CorrelationMiddleware:
    """
    Middleware that manages request, correlation, and trace identifiers.

    This middleware manages four semantically distinct identifiers:
    - request_id: Scoped to a single HTTP request. Extracted from X-Request-ID
      header or generated as UUID4 if absent.
    - correlation_id: Cross-service/cross-job workflow identity. Extracted from
      X-Correlation-ID header or defaults to the request_id value for
      request-initiated workflows.
    - trace_id: Root identifier for a distributed trace. Extracted from X-Trace-ID
      header or generated as W3C-compliant 32-character hex if absent.
    - span_id: Identifier for the current trace segment. Extracted from X-Span-ID
      header or generated as W3C-compliant 16-character hex if absent.

    This is implemented as a plain ASGI middleware to avoid the overhead and
    edge-cases of BaseHTTPMiddleware (e.g., issues with StreamingResponse and
    background task cancellation).

    Security: Validates incoming IDs to prevent log/header injection.
    Reliability: Ensures identifiers are attached to the ASGI scope state, context
    variables, and outgoing responses for both successful and error outcomes.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the correlation middleware."""
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
        raw_trace_id = _extract_and_validate_id(headers.get("x-trace-id"), "X-Trace-ID")
        raw_span_id = _extract_and_validate_id(headers.get("x-span-id"), "X-Span-ID")

        request_id = raw_request_id if raw_request_id is not None else str(uuid.uuid4())
        correlation_id = raw_correlation_id if raw_correlation_id is not None else request_id
        trace_id = raw_trace_id if raw_trace_id is not None else secrets.token_hex(16)
        span_id = raw_span_id if raw_span_id is not None else secrets.token_hex(8)

        _inject_state(scope, request_id, correlation_id, trace_id, span_id)

        async def send_with_correlation_headers(message: MutableMapping[str, Any]) -> None:
            """Wrap the send callable to inject correlation headers."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                # Set values (replace existing) to avoid duplicate headers
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Correlation-ID"] = correlation_id
                response_headers["X-Trace-ID"] = trace_id
                response_headers["X-Span-ID"] = span_id

            await send(message)

        req_tokens = None
        trace_tokens = None
        try:
            # Set contextvars for downstream code (including logging)
            req_tokens = set_request_context(request_id, correlation_id)
            trace_tokens = set_trace_context(trace_id, span_id, parent_span_id=None)
            await self.app(scope, receive, send_with_correlation_headers)
        finally:
            if req_tokens is not None:
                reset_request_context(req_tokens)
            if trace_tokens is not None:
                reset_trace_context(trace_tokens)
