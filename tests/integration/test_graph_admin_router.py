"""Tests for graph admin router registration."""

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException, status  # pylint: disable=import-error
from fastapi.testclient import TestClient  # pylint: disable=import-error
from src.config.settings import get_settings

import api.routers.graph_admin as graph_admin
from api.app_factory import create_app
from api.auth import User, get_current_active_user

pytestmark = pytest.mark.integration


def _authorized_app():
    """Create an app with an active test operator."""
    app = create_app()

    def active_user() -> User:
        """Return an active test user."""
        return User(username="system_operator", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    return app


async def _post_rebuild() -> httpx.Response:
    """Post to the graph rebuild endpoint as an active operator."""
    transport = httpx.ASGITransport(app=_authorized_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        return await client.post("/api/graph/rebuild")


async def test_app_construction_with_graph_admin_router_succeeds() -> None:
    """The graph admin router must not introduce an app construction import cycle."""
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}

    assert "/api/graph/rebuild" in routes
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.post("/api/graph/rebuild")

    assert response.status_code == 401


async def test_rebuild_returns_429_when_rebuild_already_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent rebuild requests should fail fast instead of queueing."""
    graph_admin._REBUILD_RUNTIME.mark_busy()  # pylint: disable=protected-access
    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"), pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="system_operator", disabled=False))
    finally:
        graph_admin._REBUILD_RUNTIME.mark_idle()  # pylint: disable=protected-access

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "A graph rebuild is already in progress. Please try again later."

    audit_records = [record for record in caplog.records if record.getMessage() == "graph_rebuild_audit"]
    requested_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_requested"
    ]
    rejected_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_rejected"
    ]

    assert len(requested_records) == 1
    assert len(rejected_records) == 1
    assert requested_records[0].user_ref == "system_operator"
    assert requested_records[0].path == "/api/graph/rebuild"
    assert rejected_records[0].reason == "rebuild_in_progress"
    assert rejected_records[0].status_code == 429


def test_resolve_user_ref_is_bounded_and_sanitized() -> None:
    """User references should be printable, single-line, and length bounded."""
    malicious_username = "system_operator\nFORGED=1\r\t" + ("x" * 200)
    resolved = graph_admin._resolve_user_ref(  # pylint: disable=protected-access
        User(username=malicious_username, disabled=False)
    )

    assert "\n" not in resolved
    assert "\r" not in resolved
    assert "\t" not in resolved
    assert len(resolved) <= 64
    assert resolved.startswith("system_operator_FORGED=1__")


async def test_rebuild_outcome_logging_survives_request_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Executor callback should log success even when the awaiting task is cancelled."""
    response = graph_admin.GraphRebuildResponse(
        status="persisted",
        source="sample",
        asset_count=1,
        relationship_count=0,
        regulatory_event_count=0,
    )

    def slow_success(
        _settings: graph_admin.GraphLifecycleSettings,
    ) -> graph_admin.GraphRebuildResponse:
        """Simulate rebuild work that completes after await cancellation."""
        time.sleep(0.05)
        return response

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", slow_success)

    settings = graph_admin.GraphLifecycleSettings(
        asset_graph_database_url=None,
        graph_cache_path=None,
        real_data_cache_path=None,
        use_real_data_fetcher=False,
    )

    graph_admin._REBUILD_RUNTIME.mark_busy()  # pylint: disable=protected-access

    try:
        loop = asyncio.get_running_loop()
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"):
            task = asyncio.create_task(
                graph_admin._run_rebuild_in_executor(  # pylint: disable=protected-access
                    loop,
                    settings,
                    user_ref="system_operator",
                    started_at=time.perf_counter(),
                )
            )
            await asyncio.sleep(0.01)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            # Allow time for the executor thread to finish and log
            await asyncio.sleep(0.12)
    finally:
        graph_admin.shutdown_rebuild_executor()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle()  # pylint: disable=protected-access

    audit_records = [record for record in caplog.records if record.getMessage() == "graph_rebuild_audit"]

    succeeded_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_succeeded"
    ]

    failed_records = [record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_failed"]

    assert len(succeeded_records) == 1
    assert len(failed_records) == 0
    assert succeeded_records[0].user_ref == "system_operator"
    assert succeeded_records[0].status_code == 200


# --- Operator Authorization Boundary Tests ---


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Ensure the expected admin username is set for the test environment."""
    settings = get_settings()
    # Force the admin username so tests are deterministic regardless of local .env
    monkeypatch.setattr(settings, "admin_username", "system_operator", raising=False)
    return settings


@pytest.fixture
def non_operator_client(mock_settings: Any) -> TestClient:
    """Client authenticated as a standard, non-operator active user."""
    app = create_app()

    def active_user() -> User:
        return User(username="standard_analyst", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user

    with TestClient(app) as client:
        yield client


@pytest.fixture
def operator_client(mock_settings: Any) -> TestClient:
    """Client authenticated as the authorized operator user."""
    app = create_app()

    def active_operator() -> User:
        return User(username="system_operator", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_operator

    with TestClient(app) as client:
        yield client


class TestGraphAdminOperatorBoundary:
    """Verify operator boundaries on destructive graph endpoints."""

    def test_rebuild_graph_unauthenticated_returns_401(self) -> None:
        """Unauthenticated requests must be rejected immediately."""
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/api/graph/rebuild")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rebuild_graph_forbidden_for_non_operator(self, non_operator_client: TestClient) -> None:
        """An active user who is not the operator must receive a 403."""
        response = non_operator_client.post("/api/graph/rebuild")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json().get("detail", "").lower()

    def test_rebuild_graph_allowed_for_operator(
        self,
        operator_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The configured operator user is authorized to trigger a rebuild."""
        # Mock the underlying execution to prevent actual rebuilds during auth boundary tests
        monkeypatch.setattr(
            "api.routers.graph_admin._perform_rebuild_and_persist_sync",
            lambda *args, **kwargs: None,
        )

        response = operator_client.post("/api/graph/rebuild")

        # Assert the request passed the auth boundary
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED)
