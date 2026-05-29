"""Context propagation for request and correlation identifiers."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

# Context variables for request-scoped identifiers
# request_id: Unique identifier for a single HTTP request
# correlation_id: Cross-service/cross-job workflow identity
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_request_id() -> str | None:
    """Return the current request ID from context."""
    return _request_id_ctx.get()


def get_correlation_id() -> str | None:
    """Return the current correlation ID from context."""
    return _correlation_id_ctx.get()


def get_request_context() -> dict[str, Any]:
    """
    Return a dictionary of the current request metadata.

    Useful for structured logging to ensure all log entries within a request
    contain the necessary identifiers.
    """
    return {
        "request_id": get_request_id(),
        "correlation_id": get_correlation_id(),
    }


def set_request_context(request_id: str, correlation_id: str) -> tuple[Any, Any]:
    """
    Set the request context variables.

    Returns:
        A tuple of tokens that can be used to reset the context variables.
    """
    t1 = _request_id_ctx.set(request_id)
    t2 = _correlation_id_ctx.set(correlation_id)
    return t1, t2


def reset_request_context(tokens: tuple[Any, Any]) -> None:
    """
    Reset the request context variables using the provided tokens.

    Args:
        tokens: The tokens returned by set_request_context.
    """
    t1, t2 = tokens
    _request_id_ctx.reset(t1)
    _correlation_id_ctx.reset(t2)
