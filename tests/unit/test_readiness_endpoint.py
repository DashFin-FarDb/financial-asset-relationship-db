"""Unit tests for the strict GET /api/ready readiness probe endpoint."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from api.api_models import DatabaseHealthResponse, GraphHealthResponse
from api.routers.system import readiness_check


@pytest.mark.asyncio
async def test_readiness_returns_200_when_graph_and_db_healthy() -> None:
    """Readiness returns 200 with status='ready' when both graph and DB checks pass."""
    graph_ok = GraphHealthResponse(available=True, lifecycle_state="ready", asset_count=13, relationship_count=19)
    db_ok = DatabaseHealthResponse(configured=True, type="sqlite", reachable=True)

    with (
        patch("api.routers.system._get_graph_health", return_value=graph_ok),
        patch("api.routers.system._get_database_health", return_value=db_ok),
    ):
        response = await readiness_check()

    assert response.status_code == 200
    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "ready"
    assert body["checks"]["graph"]["available"] is True
    assert body["checks"]["graph"]["asset_count"] == 13
    assert body["checks"]["database"]["reachable"] is True


@pytest.mark.asyncio
async def test_readiness_returns_503_when_graph_unavailable() -> None:
    """Readiness returns 503 with status='not_ready' when no published graph is loaded."""
    graph_down = GraphHealthResponse(
        available=False, lifecycle_state="initializing", asset_count=0, relationship_count=0
    )
    db_ok = DatabaseHealthResponse(configured=True, type="postgresql", reachable=True)

    with (
        patch("api.routers.system._get_graph_health", return_value=graph_down),
        patch("api.routers.system._get_database_health", return_value=db_ok),
    ):
        response = await readiness_check()

    assert response.status_code == 503
    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "not_ready"
    assert body["checks"]["graph"]["available"] is False


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_unreachable() -> None:
    """Readiness returns 503 with status='not_ready' when the database check fails."""
    graph_ok = GraphHealthResponse(available=True, lifecycle_state="ready", asset_count=13, relationship_count=19)
    db_down = DatabaseHealthResponse(configured=True, type="postgresql", reachable=False)

    with (
        patch("api.routers.system._get_graph_health", return_value=graph_ok),
        patch("api.routers.system._get_database_health", return_value=db_down),
    ):
        response = await readiness_check()

    assert response.status_code == 503
    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["reachable"] is False
