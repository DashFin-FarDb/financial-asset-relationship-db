"""Unit tests for CorrelationMiddleware."""

import re
import uuid
from typing import Callable

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.middleware.correlation import CorrelationMiddleware
from src.observability.context import get_correlation_id, get_request_id, get_span_id, get_trace_id


def test_correlation_middleware_logic():
    """Test that CorrelationMiddleware correctly manages IDs."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test")
    async def test_route(request: Request):
        """Mock route that returns IDs from context and state."""
        return {
            "ctx_request_id": get_request_id(),
            "ctx_correlation_id": get_correlation_id(),
            "ctx_trace_id": get_trace_id(),
            "ctx_span_id": get_span_id(),
            "state_request_id": request.state.request_id,
            "state_correlation_id": request.state.correlation_id,
            "state_trace_id": getattr(request.state, "trace_id", None),
            "state_span_id": getattr(request.state, "span_id", None),
        }

    client = TestClient(app)

    # Case 1: No headers provided (should generate IDs)
    response = client.get("/test")
    assert response.status_code == 200
    data = response.json()

    req_id = response.headers.get("X-Request-ID")
    corr_id = response.headers.get("X-Correlation-ID")
    trace_id = response.headers.get("X-Trace-ID")
    span_id = response.headers.get("X-Span-ID")

    assert req_id is not None
    assert corr_id is not None
    assert trace_id is not None
    assert span_id is not None
    assert req_id == corr_id
    assert data["ctx_request_id"] == req_id
    assert data["ctx_correlation_id"] == corr_id
    assert data["ctx_trace_id"] == trace_id
    assert data["ctx_span_id"] == span_id
    assert data["state_request_id"] == req_id
    assert data["state_correlation_id"] == corr_id
    assert data["state_trace_id"] == trace_id
    assert data["state_span_id"] == span_id

    # Case 2: Headers provided (should respect them)
    custom_req_id = "custom-req-id"
    custom_corr_id = "custom-corr-id"
    custom_trace_id = "0123456789abcdef0123456789abcdef"
    custom_span_id = "0123456789abcdef"
    response = client.get(
        "/test",
        headers={
            "X-Request-ID": custom_req_id,
            "X-Correlation-ID": custom_corr_id,
            "X-Trace-ID": custom_trace_id,
            "X-Span-ID": custom_span_id,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert response.headers.get("X-Request-ID") == custom_req_id
    assert response.headers.get("X-Correlation-ID") == custom_corr_id
    assert response.headers.get("X-Trace-ID") == custom_trace_id
    assert response.headers.get("X-Span-ID") == custom_span_id
    assert data["ctx_request_id"] == custom_req_id
    assert data["ctx_correlation_id"] == custom_corr_id
    assert data["ctx_trace_id"] == custom_trace_id
    assert data["ctx_span_id"] == custom_span_id

    # Case 3: Only Correlation ID provided (Request ID should be generated)
    response = client.get(
        "/test",
        headers={
            "X-Correlation-ID": "only-corr",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert response.headers.get("X-Correlation-ID") == "only-corr"
    assert response.headers.get("X-Request-ID") != "only-corr"
    assert data["ctx_correlation_id"] == "only-corr"
    assert data["ctx_request_id"] == response.headers.get("X-Request-ID")

    # Case 4: Invalid/Dangerous headers (should be rejected and replaced with generated IDs)
    dangerous_id = "dangerous-id'; DROP TABLE users; --"
    long_id = "a" * 100
    response = client.get(
        "/test",
        headers={
            "X-Request-ID": dangerous_id,
            "X-Correlation-ID": long_id,
            "X-Trace-ID": dangerous_id,
            "X-Span-ID": long_id,
        },
    )
    assert response.status_code == 200

    # Should have generated new IDs instead of using dangerous/long ones
    assert response.headers.get("X-Request-ID") != dangerous_id
    assert response.headers.get("X-Correlation-ID") != long_id
    assert response.headers.get("X-Trace-ID") != dangerous_id
    assert response.headers.get("X-Span-ID") != long_id
    assert is_valid_uuid(response.headers.get("X-Request-ID"))
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers.get("X-Trace-ID"))
    assert re.fullmatch(r"[0-9a-f]{16}", response.headers.get("X-Span-ID"))

    # Case 5: Extremely long headers (DoS prevention)
    very_long_id = "a" * 2000
    response = client.get(
        "/test",
        headers={
            "X-Request-ID": very_long_id,
            "X-Correlation-ID": very_long_id,
        },
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") != very_long_id
    assert response.headers.get("X-Correlation-ID") != very_long_id
    assert is_valid_uuid(response.headers.get("X-Request-ID"))


@pytest.mark.asyncio
async def test_correlation_middleware_cleanup_on_error() -> None:
    """Test that context is reset even if the downstream app raises an exception."""

    async def failing_app(scope: dict, receive: Callable, send: Callable) -> None:
        """Simulate a downstream ASGI app that raises an exception."""
        raise ValueError("Simulated downstream error")

    middleware = CorrelationMiddleware(failing_app)  # type: ignore[arg-type]
    scope = {"type": "http", "headers": [], "state": {}}

    async def mock_receive():
        """Mock ASGI receive function."""
        return {}

    async def mock_send(msg):
        """Mock ASGI send function."""
        ...

    with pytest.raises(ValueError, match="Simulated downstream error"):
        await middleware(scope, mock_receive, mock_send)

    # After exception, context should be empty
    assert get_request_id() is None
    assert get_correlation_id() is None
    assert get_trace_id() is None
    assert get_span_id() is None


@pytest.mark.asyncio
async def test_correlation_middleware_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that if set_trace_context raises, request context is still reset."""
    from api.middleware import correlation

    def failing_set_trace_context(*args, **kwargs):
        """Mock set_trace_context to simulate a failure."""
        raise RuntimeError("simulated set_trace_context failure")

    monkeypatch.setattr(correlation, "set_trace_context", failing_set_trace_context)

    async def mock_app(scope: dict, receive: Callable, send: Callable) -> None:
        """Mock ASGI app that does nothing."""
        pass

    middleware = CorrelationMiddleware(mock_app)  # type: ignore[arg-type]
    scope = {"type": "http", "headers": [], "state": {}}

    async def mock_receive():
        """Mock ASGI receive function."""
        return {}

    async def mock_send(msg):
        """Mock ASGI send function."""
        ...

    with pytest.raises(RuntimeError, match="simulated set_trace_context failure"):
        await middleware(scope, mock_receive, mock_send)

    # After exception, request context should be empty
    assert get_request_id() is None
    assert get_correlation_id() is None
    # Note: Tokens generated for trace/span IDs are lowercase W3C-compliant hex.


@pytest.mark.asyncio
async def test_correlation_middleware_state_fallback() -> None:  # noqa: C901
    """Test state injection fallback paths in CorrelationMiddleware."""

    async def mock_app(scope: dict, receive: Callable, send: Callable) -> None:
        """Mock ASGI application that does nothing."""

    middleware = CorrelationMiddleware(mock_app)  # type: ignore[arg-type]

    from collections.abc import MutableMapping

    class FailingMutableMapping(MutableMapping):
        """A mutable mapping that raises KeyError on get and TypeError on set."""

        def __init__(self):
            self.request_id = None
            self.correlation_id = None
            self.trace_id = None
            self.span_id = None

        def __getitem__(self, key):
            raise KeyError(key)

        def __setitem__(self, key, value):
            raise TypeError("Read-only mapping")

        def __delitem__(self, key):
            raise TypeError("Read-only mapping")

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

    state_obj = FailingMutableMapping()
    scope = {"type": "http", "headers": [(b"x-request-id", b"fallback-req-1")], "state": state_obj}

    async def mock_receive():
        """Mock ASGI receive function."""
        return {}

    async def mock_send(msg):
        """Mock ASGI send function."""

    await middleware(scope, mock_receive, mock_send)

    # Should have fallen back to attribute assignment
    assert getattr(state_obj, "request_id", None) == "fallback-req-1"
    assert getattr(state_obj, "correlation_id", None) == "fallback-req-1"
    assert getattr(state_obj, "trace_id", None) is not None
    assert getattr(state_obj, "span_id", None) is not None

    # 2. Test with object that raises on setattr too (ensure it continues safely)
    class CompletelyFailingState(MutableMapping):
        """A mutable mapping that raises errors on all operations."""

        def __getitem__(self, key):
            raise KeyError(key)

        def __setitem__(self, key, value):
            raise TypeError("Read-only mapping")

        def __delitem__(self, key):
            raise TypeError("Read-only mapping")

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

        def __setattr__(self, name, value):
            raise AttributeError("Read-only attributes")

    state_obj2 = CompletelyFailingState()
    scope2 = {"type": "http", "headers": [(b"x-request-id", b"fallback-req-2")], "state": state_obj2}

    await middleware(scope2, mock_receive, mock_send)
    # The middleware should catch the exception and continue normally without raising
    # Verification is simply that we reached this point without a crash.


def is_valid_uuid(val: str | None) -> bool:
    """Return whether val is a valid UUID string."""
    if val is None:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


def test_correlation_id_validation_rejects_newlines() -> None:
    """Test that is_valid_id rejects CRLF or newline injected headers."""
    from src.observability.context import is_valid_id

    assert is_valid_id("valid-id-123") is True
    assert is_valid_id("invalid-id\r\nInjected-Header: true") is False
    assert is_valid_id("invalid-id\nInjected") is False


@pytest.mark.asyncio
async def test_correlation_middleware_header_deduplication() -> None:
    """Test that CorrelationMiddleware deduplicates headers if downstream already sets them."""

    async def mock_app(scope: dict, receive: Callable, send: Callable) -> None:
        """Mock ASGI app that sets custom headers."""
        # Downstream app sets its own headers
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"x-request-id", b"downstream-req-id"),
                    (b"x-correlation-id", b"downstream-corr-id"),
                ],
            }
        )

    middleware = CorrelationMiddleware(mock_app)  # type: ignore[arg-type]
    scope = {"type": "http", "headers": [], "state": {}}

    async def mock_receive():
        """Mock ASGI receive function."""
        return {}

    sent_messages = []

    async def mock_send(msg):
        """Mock ASGI send function."""
        sent_messages.append(msg)

    await middleware(scope, mock_receive, mock_send)

    assert len(sent_messages) > 0
    start_msg = sent_messages[0]

    # Assert there's only one request-id and correlation-id header, and it matches the middleware-generated one
    raw_headers = [k for k, v in start_msg.get("headers", [])]
    assert raw_headers.count(b"x-request-id") == 1
    assert raw_headers.count(b"x-correlation-id") == 1
    assert raw_headers.count(b"x-trace-id") == 1
    assert raw_headers.count(b"x-span-id") == 1
