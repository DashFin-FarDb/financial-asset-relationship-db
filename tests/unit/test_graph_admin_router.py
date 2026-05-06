"""Tests for graph admin router registration."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.unit


async def test_app_construction_with_graph_admin_router_succeeds() -> None:
    """The graph admin router must not introduce an app construction import cycle."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/graph/rebuild" in routes
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/graph/rebuild")

    assert response.status_code == 401
