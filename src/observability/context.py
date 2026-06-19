"""Context propagation for request and correlation identifiers."""

from __future__ import annotations

import contextlib
import re
from collections.abc import AsyncIterator, Iterator
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextvars import Token

# Validation regex for correlation/request IDs to prevent log injection
# Allows alphanumeric, hyphen, underscore, and dot, length 1-64
_ID_VALIDATION_REGEX = re.compile(r"^[a-zA-Z0-9\-_\.]{1,64}$")

# Context variables for request-scoped identifiers
# request_id: Unique identifier for a single HTTP request
# correlation_id: Cross-service/cross-job workflow identity
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Context variables for trace identifiers
# trace_id: Root identifier for a distributed trace
# span_id: Identifier for the current trace segment
# parent_span_id: Parent span identifier (if nested)
_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id_ctx: ContextVar[str | None] = ContextVar("span_id", default=None)
_parent_span_id_ctx: ContextVar[str | None] = ContextVar("parent_span_id", default=None)


def is_valid_id(identifier: str | None) -> bool:
    """Return whether the identifier matches the security validation policy."""
    if not identifier:
        return False
    return bool(_ID_VALIDATION_REGEX.match(identifier))


def get_request_id() -> str | None:
    """Return the current request ID from context."""
    return _request_id_ctx.get()


def get_correlation_id() -> str | None:
    """Return the current correlation ID from context."""
    return _correlation_id_ctx.get()


def get_trace_id() -> str | None:
    """Return the current trace ID from context."""
    return _trace_id_ctx.get()


def get_span_id() -> str | None:
    """Return the current span ID from context."""
    return _span_id_ctx.get()


def get_parent_span_id() -> str | None:
    """Return the current parent span ID from context."""
    return _parent_span_id_ctx.get()


def get_request_context() -> dict[str, str | None]:
    """
    Return a dictionary of the current request metadata.

    Useful for structured logging to ensure all log entries within a request
    contain the necessary identifiers.
    """
    return {
        "request_id": get_request_id(),
        "correlation_id": get_correlation_id(),
        "trace_id": get_trace_id(),
        "span_id": get_span_id(),
        "parent_span_id": get_parent_span_id(),
    }


def set_request_context(request_id: str, correlation_id: str) -> tuple[Token[str | None], Token[str | None]]:
    """
    Set the request context variables.

    Returns:
        A tuple of tokens that can be used to reset the context variables.
    """
    t1 = _request_id_ctx.set(request_id)
    t2 = _correlation_id_ctx.set(correlation_id)
    return t1, t2


def reset_request_context(tokens: tuple[Token[str | None], Token[str | None]]) -> None:
    """
    Reset the request context variables using the provided tokens.

    Args:
        tokens: The tokens returned by set_request_context.
    """
    t1, t2 = tokens
    _request_id_ctx.reset(t1)
    _correlation_id_ctx.reset(t2)


def set_trace_context(
    trace_id: str | None,
    span_id: str | None,
    parent_span_id: str | None = None,
) -> tuple[Token[str | None], Token[str | None], Token[str | None]]:
    """
    Set the trace context variables (trace_id, span_id, parent_span_id).

    Validates identifiers against the security policy before setting them.
    Invalid or unvalidated identifiers default to None to prevent log injection.

    Returns:
        A tuple of tokens that can be used to reset the context variables.
    """
    safe_trace_id = trace_id if is_valid_id(trace_id) else None
    safe_span_id = span_id if is_valid_id(span_id) else None
    safe_parent_span_id = parent_span_id if is_valid_id(parent_span_id) else None

    t1 = _trace_id_ctx.set(safe_trace_id)
    t2 = _span_id_ctx.set(safe_span_id)
    t3 = _parent_span_id_ctx.set(safe_parent_span_id)
    return t1, t2, t3


def reset_trace_context(
    tokens: tuple[Token[str | None], Token[str | None], Token[str | None]],
) -> None:
    """
    Reset the trace context variables using the provided tokens.

    Args:
        tokens: The tokens returned by set_trace_context.
    """
    t1, t2, t3 = tokens
    _trace_id_ctx.reset(t1)
    _span_id_ctx.reset(t2)
    _parent_span_id_ctx.reset(t3)


@contextlib.contextmanager
def trace_context(
    trace_id: str | None,
    span_id: str | None,
    parent_span_id: str | None = None,
) -> Iterator[None]:
    """
    Context manager to set and automatically reset trace context variables.

    Example:
        with trace_context("trace-1", "span-1"):
            # Execute traced operation
            pass
    """
    tokens = set_trace_context(trace_id, span_id, parent_span_id)
    try:
        yield
    finally:
        reset_trace_context(tokens)


@contextlib.asynccontextmanager
async def async_trace_context(
    trace_id: str | None,
    span_id: str | None,
    parent_span_id: str | None = None,
) -> AsyncIterator[None]:
    """
    Async context manager to set and automatically reset trace context variables.

    Example:
        async with async_trace_context("trace-1", "span-1"):
            # Execute traced async operation
            pass
    """
    tokens = set_trace_context(trace_id, span_id, parent_span_id)
    try:
        yield
    finally:
        reset_trace_context(tokens)


@contextlib.contextmanager
def request_context(request_id: str, correlation_id: str) -> Iterator[None]:
    """Context manager to set and automatically reset request context variables."""
    tokens = set_request_context(request_id, correlation_id)
    try:
        yield
    finally:
        reset_request_context(tokens)


@contextlib.asynccontextmanager
async def async_request_context(request_id: str, correlation_id: str) -> AsyncIterator[None]:
    """Async context manager to set and automatically reset request context variables."""
    tokens = set_request_context(request_id, correlation_id)
    try:
        yield
    finally:
        reset_request_context(tokens)
