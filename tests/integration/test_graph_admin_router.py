"""Tests for graph admin router registration."""

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException  # pylint: disable=import-error

import api.routers.graph_admin as graph_admin
from api.auth import User, get_current_active_user

pytestmark = pytest.mark.integration


def _authorized_app():
    """Create an app with an active test operator."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()

    def active_user() -> User:
        """Return an active test user."""
        return User(username="operator", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    return app


async def _post_rebuild() -> httpx.Response:
    """Post to the graph rebuild endpoint as an active operator."""
    transport = httpx.ASGITransport(app=_authorized_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        return await client.post("/api/graph/rebuild")


async def test_app_construction_with_graph_admin_router_succeeds() -> None:
    """The graph admin router must not introduce an app construction import cycle."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/graph/rebuild" in routes
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.post("/api/graph/rebuild")

    assert response.status_code == 401


async def test_rebuild_returns_429_when_rebuild_already_running() -> None:
    """Concurrent rebuild requests should fail fast instead of queueing."""
    graph_admin._REBUILD_RUNTIME.mark_busy()  # pylint: disable=protected-access
    try:
        with pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="operator", disabled=False))
    finally:
        graph_admin._REBUILD_RUNTIME.mark_idle()  # pylint: disable=protected-access

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "A graph rebuild is already in progress. Please try again later."
