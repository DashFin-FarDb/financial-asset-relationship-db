"""Middleware for managing request and correlation identifiers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders

from src.observability.context import is_valid_id, reset_request_context, set_request_context
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


MAX_HEADER_LENGTH = 1024
LOG_TRUNCATE_LEN = 200


def _extract_and_validate_id(raw_id: str | None, header_name: str) -> str | None:
    """
    Validate and return a trimmed identifier extracted from an incoming header, or `None` if the value is not acceptable.
    
    If `raw_id` is not a string, the function returns `None`. Values whose original length exceeds `MAX_HEADER_LENGTH` are rejected and a `correlation_id_oversized_header` observability event is emitted. The header value is trimmed of surrounding whitespace and validated; if validation fails, a `correlation_id_invalid_header` observability event is emitted.
    
    Parameters:
        raw_id (str | None): The raw header value to validate.
        header_name (str): The header name used in observability event metadata and messages.
    
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


def _inject_state(scope: Scope, request_id: str, correlation_id: str) -> None:
    """
    Attach request_id and correlation_id to the ASGI scope's state for downstream handlers.
    
    Attempts to write the identifiers into scope["state"] in a way compatible with FastAPI's Request.state:
    - If scope has no "state", the function returns without side effects.
    - If the state object is a mapping, it first tries mapping-style writes and falls back to attribute-style assignment on failure.
    - If the state object is not a mapping, it attempts attribute-style assignment only.
    - Failures to attach IDs do not raise; the function logs structured observability events for skipped injection, mapping errors, attribute-assignment failures, and other unexpected errors.
    
    Parameters:
        scope (Scope): The ASGI connection scope; the function reads and may modify scope["state"].
        request_id (str): The request identifier to attach to the state.
        correlation_id (str): The correlation identifier to attach to the state.
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
    if isinstance(state_obj, MutableMapping):
        try:
            state_obj["request_id"] = request_id
            state_obj["correlation_id"] = correlation_id
        except (TypeError, AttributeError) as assign_exc:
            # Fallback to attribute-style assignment for objects that don't support mapping writes
            try:
                setattr(state_obj, "request_id", request_id)
                setattr(state_obj, "correlation_id", correlation_id)
            except (TypeError, AttributeError) as attr_exc:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="correlation_id_state_injection_failed",
                        message=(
                            f"Could not attach correlation IDs to state object of type {type(state_obj).__name__} "
                            f"(map_err={type(assign_exc).__name__}, attr_err={type(attr_exc).__name__}); "
                            "continuing without state injection"
                        ),
                        metadata={
                            "state_type": type(state_obj).__name__,
                            "map_err": type(assign_exc).__name__,
                            "attr_err": type(attr_exc).__name__,
                        },
                    ),
                )
            except Exception as exc:
                # Unexpected error while falling back to attribute assignment; log at debug to avoid
                # noisy traceback for non-fatal state injection errors.
                log_event(
                    logger,
                    logging.DEBUG,
                    ObservabilityEvent(
                        event="correlation_id_state_injection_fallback_error",
                        message=(
                            f"Unexpected error while falling back to attribute assignment for state "
                            f"object {type(state_obj).__name__}: {type(exc).__name__}"
                        ),
                        metadata={"state_type": type(state_obj).__name__, "error": type(exc).__name__},
                    ),
                )
        except Exception as exc:
            # Unexpected error while assigning into mapping; log at debug to avoid noisy
            # traceback for non-fatal state injection errors.
            log_event(
                logger,
                logging.DEBUG,
                ObservabilityEvent(
                    event="correlation_id_state_injection_mapping_error",
                    message=(
                        "Unexpected error while assigning into mapping-style state "
                        f"object {type(state_obj).__name__}: {type(exc).__name__}"
                    ),
                    metadata={"state_type": type(state_obj).__name__, "error": type(exc).__name__},
                ),
            )
    else:
        try:
            setattr(state_obj, "request_id", request_id)
            setattr(state_obj, "correlation_id", correlation_id)
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
