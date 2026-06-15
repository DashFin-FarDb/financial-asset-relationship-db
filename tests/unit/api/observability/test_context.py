"""Unit tests for context propagation."""

import asyncio

import pytest

from src.observability.context import (
    get_correlation_id,
    get_parent_span_id,
    get_request_context,
    get_request_id,
    get_span_id,
    get_trace_id,
    is_valid_id,
    request_context,
    reset_request_context,
    reset_trace_context,
    set_request_context,
    set_trace_context,
    trace_context,
)


def test_request_context_management():
    """Test setting, getting, and resetting request context."""
    # Initially None
    assert get_request_id() is None
    assert get_correlation_id() is None
    assert get_request_context() == {
        "request_id": None,
        "correlation_id": None,
        "trace_id": None,
        "span_id": None,
        "parent_span_id": None,
    }

    # Set context
    request_id = "test-req-123"
    correlation_id = "test-corr-456"
    tokens = set_request_context(request_id, correlation_id)

    try:
        assert get_request_id() == request_id
        assert get_correlation_id() == correlation_id
        assert get_request_context() == {
            "request_id": request_id,
            "correlation_id": correlation_id,
            "trace_id": None,
            "span_id": None,
            "parent_span_id": None,
        }
    finally:
        # Reset context in finally to prevent leakage even if assertions fail
        reset_request_context(tokens)

    assert get_request_id() is None
    assert get_correlation_id() is None


def test_trace_context_management():
    """Test setting, getting, and resetting trace context."""
    assert get_trace_id() is None
    assert get_span_id() is None
    assert get_parent_span_id() is None

    trace_id = "trace-123"
    span_id = "span-456"
    parent_span_id = "parent-789"
    tokens = set_trace_context(trace_id, span_id, parent_span_id)

    try:
        assert get_trace_id() == trace_id
        assert get_span_id() == span_id
        assert get_parent_span_id() == parent_span_id
        ctx = get_request_context()
        assert ctx["trace_id"] == trace_id
        assert ctx["span_id"] == span_id
        assert ctx["parent_span_id"] == parent_span_id
    finally:
        reset_trace_context(tokens)

    assert get_trace_id() is None
    assert get_span_id() is None
    assert get_parent_span_id() is None


def test_is_valid_id():
    """Test ID validation regex."""
    assert is_valid_id("valid-id_1.23") is True
    assert is_valid_id("a" * 64) is True
    assert is_valid_id("a" * 65) is False
    assert is_valid_id("invalid/id") is False
    assert is_valid_id(None) is False
    assert is_valid_id("") is False


def test_set_trace_context_validation():
    """Test that set_trace_context drops invalid identifiers."""
    tokens = set_trace_context("valid-trace", "invalid/span", None)
    try:
        assert get_trace_id() == "valid-trace"
        assert get_span_id() is None
        assert get_parent_span_id() is None
    finally:
        reset_trace_context(tokens)


@pytest.mark.asyncio
async def test_async_context_isolation():
    """Test that context variables are isolated across async tasks."""

    async def worker(req_id: str, trace_id: str) -> dict[str, str | None]:
        req_tokens = set_request_context(req_id, f"corr-{req_id}")
        trace_tokens = set_trace_context(trace_id, f"span-{trace_id}", None)
        try:
            # Yield to event loop
            await asyncio.sleep(0.01)
            return get_request_context()
        finally:
            reset_trace_context(trace_tokens)
            reset_request_context(req_tokens)

    results = await asyncio.gather(
        worker("req1", "trace1"),
        worker("req2", "trace2"),
    )

    assert results[0] == {
        "request_id": "req1",
        "correlation_id": "corr-req1",
        "trace_id": "trace1",
        "span_id": "span-trace1",
        "parent_span_id": None,
    }
    assert results[1] == {
        "request_id": "req2",
        "correlation_id": "corr-req2",
        "trace_id": "trace2",
        "span_id": "span-trace2",
        "parent_span_id": None,
    }


def test_trace_context_manager():
    """Test the trace_context context manager."""
    assert get_trace_id() is None
    with trace_context("cm-trace", "cm-span"):
        assert get_trace_id() == "cm-trace"
        assert get_span_id() == "cm-span"
        assert get_parent_span_id() is None
    assert get_trace_id() is None


def test_request_context_manager():
    """Test the request_context context manager."""
    assert get_request_id() is None
    with request_context("cm-req", "cm-corr"):
        assert get_request_id() == "cm-req"
        assert get_correlation_id() == "cm-corr"
    assert get_request_id() is None
