"""Integration tests for the tracing middleware and context propagation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.tracing_middleware import TracingMiddleware
from src.observability.context import get_request_context


def _make_app():
    app = FastAPI()
    app.add_middleware(TracingMiddleware)

    @app.get("/ctx")
    async def ctx():
        return get_request_context()

    return app


def test_tracing_middleware_with_headers():
    app = _make_app()
    client = TestClient(app)

    headers = {
        "x-request-id": "test-req",
        "x-correlation-id": "test-corr",
        "x-trace-id": "test-trace",
        "x-span-id": "test-span",
    }

    resp = client.get("/ctx", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == "test-req"
    assert data["correlation_id"] == "test-corr"
    assert data["trace_id"] == "test-trace"
    assert data["span_id"] == "test-span"


def test_tracing_middleware_generates_ids_when_absent():
    app = _make_app()
    client = TestClient(app)

    resp = client.get("/ctx")
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] is not None
    assert data["correlation_id"] is not None
    assert data["request_id"].startswith("req-")
    assert data["correlation_id"].startswith("corr-")
