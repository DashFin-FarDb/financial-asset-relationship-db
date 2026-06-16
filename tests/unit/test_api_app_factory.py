"""Tests for api/app_factory.py."""

import pytest

from api.app_factory import _run_with_generated_trace
from src.observability.context import get_span_id, get_trace_id


@pytest.mark.asyncio
async def test_run_with_generated_trace_success():
    """Test that a callable executes within a generated trace context."""

    def dummy_task():
        """Return the trace ID and span ID to verify context variables."""
        # Inside the callable, the context vars should be populated
        return get_trace_id(), get_span_id()

    trace_id, span_id, result = await _run_with_generated_trace(dummy_task)

    # Verify that the generated IDs match what the function saw internally
    assert result[0] == trace_id
    assert result[1] == span_id

    # Ensure they are valid IDs (not None)
    assert trace_id is not None
    assert span_id is not None


@pytest.mark.asyncio
async def test_run_with_generated_trace_exception():
    """Test that exceptions raised are stamped with trace_id and span_id."""

    def failing_task():
        """Raise a ValueError to simulate a failure."""
        raise ValueError("simulated error")

    with pytest.raises(ValueError) as exc_info:
        await _run_with_generated_trace(failing_task)

    # Verify that the exception caught has trace_id and span_id attributes attached
    assert hasattr(exc_info.value, "trace_id")
    assert hasattr(exc_info.value, "span_id")
    assert exc_info.value.trace_id is not None
    assert exc_info.value.span_id is not None
