"""Unit tests for context propagation."""

from api.observability.context import (
    get_correlation_id,
    get_request_context,
    get_request_id,
    reset_request_context,
    set_request_context,
)


def test_request_context_management():
    """Test setting, getting, and resetting request context."""
    # Initially None
    assert get_request_id() is None
    assert get_correlation_id() is None
    assert get_request_context() == {"request_id": None, "correlation_id": None}

    # Set context
    request_id = "test-req-123"
    correlation_id = "test-corr-456"
    tokens = set_request_context(request_id, correlation_id)

    assert get_request_id() == request_id
    assert get_correlation_id() == correlation_id
    assert get_request_context() == {
        "request_id": request_id,
        "correlation_id": correlation_id,
    }

    # Reset context
    reset_request_context(tokens)

    assert get_request_id() is None
    assert get_correlation_id() is None
