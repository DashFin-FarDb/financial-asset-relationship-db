"""Unit tests for CorrelationMiddleware."""

import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.middleware.correlation import CorrelationMiddleware
from src.observability.context import get_correlation_id, get_request_id


def test_correlation_middleware_logic():
    """Test that CorrelationMiddleware correctly manages IDs."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test")
    async def test_route(request: Request):
        return {
            "ctx_request_id": get_request_id(),
            "ctx_correlation_id": get_correlation_id(),
            "state_request_id": request.state.request_id,
            "state_correlation_id": request.state.correlation_id,
        }

    client = TestClient(app)

    # Case 1: No headers provided (should generate IDs)
    response = client.get("/test")
    assert response.status_code == 200
    data = response.json()

    req_id = response.headers.get("X-Request-ID")
    corr_id = response.headers.get("X-Correlation-ID")

    assert req_id is not None
    assert corr_id is not None
    assert req_id == corr_id
    assert data["ctx_request_id"] == req_id
    assert data["ctx_correlation_id"] == corr_id
    assert data["state_request_id"] == req_id
    assert data["state_correlation_id"] == corr_id

    # Case 2: Headers provided (should respect them)
    custom_req_id = "custom-req-id"
    custom_corr_id = "custom-corr-id"
    response = client.get(
        "/test",
        headers={
            "X-Request-ID": custom_req_id,
            "X-Correlation-ID": custom_corr_id,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert response.headers.get("X-Request-ID") == custom_req_id
    assert response.headers.get("X-Correlation-ID") == custom_corr_id
    assert data["ctx_request_id"] == custom_req_id
    assert data["ctx_correlation_id"] == custom_corr_id

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
        },
    )
    assert response.status_code == 200

    # Should have generated new IDs instead of using dangerous/long ones
    assert response.headers.get("X-Request-ID") != dangerous_id
    assert response.headers.get("X-Correlation-ID") != long_id
    assert is_valid_uuid(response.headers.get("X-Request-ID"))

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
async def test_correlation_middleware_state_fallback() -> None:
    """Test state injection fallback paths in CorrelationMiddleware."""

    async def mock_app(scope: dict, receive: callable, send: callable) -> None:
        pass

    middleware = CorrelationMiddleware(mock_app)

    from collections.abc import MutableMapping

    class FailingMutableMapping(MutableMapping):
        def __init__(self):
            self.request_id = None
            self.correlation_id = None

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
        return {}

    async def mock_send(msg):
        pass

    await middleware(scope, mock_receive, mock_send)

    # Should have fallen back to attribute assignment
    assert getattr(state_obj, "request_id", None) == "fallback-req-1"
    assert getattr(state_obj, "correlation_id", None) == "fallback-req-1"

    # 2. Test with object that raises on setattr too (ensure it continues safely)
    class CompletelyFailingState(MutableMapping):
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
