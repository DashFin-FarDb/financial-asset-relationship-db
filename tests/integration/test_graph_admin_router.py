"""Tests for graph admin router registration."""

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterator

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException  # pylint: disable=import-error
from fastapi.testclient import TestClient  # pylint: disable=import-error

import api.routers.graph_admin as graph_admin
from api.auth import (
    REBUILD_OPERATOR_FORBIDDEN_DETAIL,
    REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL,
    User,
    get_current_active_user,
)
from src.config.settings import get_settings

pytestmark = pytest.mark.integration


def _configure_test_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the test operator username and refresh cached settings."""
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    get_settings.cache_clear()


def _client_with_active_user(
    monkeypatch: pytest.MonkeyPatch,
    username: str,
) -> Iterator[TestClient]:
    """Create a client whose active user has the supplied username."""
    _configure_test_operator(monkeypatch)
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()

    def active_user() -> User:
        """Return a mock active user."""
        return User(username=username, disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user

    try:
        with TestClient(app) as client:
            yield client
    finally:
        get_settings.cache_clear()


@pytest.fixture
def non_operator_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Client authenticated as a standard, non-operator active user."""
    yield from _client_with_active_user(monkeypatch, "standard_analyst")


@pytest.fixture
def operator_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Client authenticated as the authorized operator user."""
    yield from _client_with_active_user(monkeypatch, "admin")


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


def test_rebuild_returns_403_for_active_non_operator_user(non_operator_client: TestClient) -> None:
    """Active authenticated users who are not operator-authorized should be forbidden."""
    response = non_operator_client.post("/api/graph/rebuild")
    assert response.status_code == 403
    assert response.json()["detail"] == REBUILD_OPERATOR_FORBIDDEN_DETAIL


def test_rebuild_allows_active_authorized_operator_user(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorized operator should retain rebuild happy path behavior."""

    def fake_rebuild(
        _settings: graph_admin.GraphLifecycleSettings,
    ) -> graph_admin.GraphRebuildResponse:
        """Return a mock successful GraphRebuildResponse."""
        return graph_admin.GraphRebuildResponse(
            status="persisted",
            source="sample",
            asset_count=0,
            relationship_count=0,
            regulatory_event_count=0,
        )

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", fake_rebuild)

    try:
        response = operator_client.post("/api/graph/rebuild")
    finally:
        graph_admin.shutdown_rebuild_executor()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle()  # pylint: disable=protected-access

    assert response.status_code == 200
    assert response.json() == {
        "status": "persisted",
        "source": "sample",
        "asset_count": 0,
        "relationship_count": 0,
        "regulatory_event_count": 0,
    }


@pytest.mark.parametrize("configured_admin", [None, "", "   "])
def test_rebuild_returns_503_when_operator_authorization_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    configured_admin: str | None,
) -> None:
    """Rebuild should fail closed when no operator username is configured."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    if configured_admin is None:
        monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    else:
        monkeypatch.setenv("ADMIN_USERNAME", configured_admin)

    get_settings.cache_clear()
    app = create_app()

    def active_user() -> User:
        """Return an active user used to prove fail-closed config behavior."""
        return User(username="admin", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user

    try:
        with TestClient(app) as client:
            response = client.post("/api/graph/rebuild")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["detail"] == REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL


async def test_rebuild_returns_429_when_rebuild_already_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Concurrent rebuild requests should fail fast instead of queueing."""
    graph_admin._REBUILD_RUNTIME.mark_busy()  # pylint: disable=protected-access
    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"), pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="admin", disabled=False))
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
    assert requested_records[0].user_ref == "admin"
    assert requested_records[0].path == "/api/graph/rebuild"
    assert rejected_records[0].reason == "rebuild_in_progress"
    assert rejected_records[0].status_code == 429


def test_resolve_user_ref_is_bounded_and_sanitized() -> None:
    """User references should be printable, single-line, and length bounded."""
    malicious_username = "operator\nFORGED=1\r\t" + ("x" * 200)
    resolved = graph_admin._resolve_user_ref(  # pylint: disable=protected-access
        User(username=malicious_username, disabled=False)
    )

    assert "\n" not in resolved
    assert "\r" not in resolved
    assert "\t" not in resolved
    assert len(resolved) <= 64
    assert resolved.startswith("operator_FORGED=1__")


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
                    user_ref="admin",
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
    assert succeeded_records[0].user_ref == "admin"
    assert succeeded_records[0].status_code == 200
