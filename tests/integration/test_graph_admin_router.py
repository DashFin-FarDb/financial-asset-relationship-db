"""Tests for graph admin router registration."""

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

    from src.data.repository import AssetGraphRepository


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


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


def _assert_successful_json_response(response: httpx.Response) -> dict[str, Any]:
    """Assert response is 200 OK and return the parsed JSON."""
    assert response.status_code == 200
    return response.json()


@contextlib.contextmanager
def _rebuild_jobs_db_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    """Provide a clean, initialized database and session factory for tests."""
    from src.config.settings import get_settings as get_settings_uncached
    from src.data.database import create_engine_from_url, create_session_factory, init_db

    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    settings = get_settings_uncached()
    engine = create_engine_from_url(settings.asset_graph_database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        yield session_factory
    finally:
        engine.dispose()


def _create_rebuild_jobs(
    repo: AssetGraphRepository,
    count: int,
    *,
    source_prefix: str = "test",
    numbered_sources: bool = True,
) -> list[str]:
    """Create rebuild jobs for endpoint tests and return IDs in creation order."""
    job_ids: list[str] = []
    for index in range(count):
        source = f"{source_prefix}{index}" if numbered_sources else source_prefix
        job_id = repo.create_rebuild_job(
            requested_by="operator",
            source=source,
        )
        job_ids.append(job_id)
    return job_ids


# ---------------------------------------------------------------------------
# Rebuild Action Endpoints Tests
# ---------------------------------------------------------------------------


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


async def test_rebuild_job_endpoints_require_authentication() -> None:
    """Rebuild job read endpoints must reject unauthenticated requests."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        job_response = await client.get("/api/graph/rebuild/jobs/test-job-id")
        list_response = await client.get("/api/graph/rebuild/jobs")

    assert job_response.status_code == 401
    assert list_response.status_code == 401


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
        *,
        user_ref: str,
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
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

    data = _assert_successful_json_response(response)
    assert data == {
        "status": "persisted",
        "source": "sample",
        "asset_count": 0,
        "relationship_count": 0,
        "regulatory_event_count": 0,
    }


def test_rebuild_lock_contention_does_not_mark_runtime_failed(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Distributed lock contention should return 429 while leaving runtime healthy."""

    def fake_rebuild(
        _settings: graph_admin.GraphLifecycleSettings,
        *,
        user_ref: str,
    ) -> graph_admin.GraphRebuildResponse:
        raise graph_admin._DistributedLockAcquisitionError("busy")  # pylint: disable=protected-access

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", fake_rebuild)

    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"):
            response = operator_client.post("/api/graph/rebuild")
    finally:
        graph_admin.shutdown_rebuild_executor()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

    assert response.status_code == 429
    assert graph_admin.get_runtime_lifecycle_state() == graph_admin.GraphRuntimeLifecycleState.READY

    audit_records = [record for record in caplog.records if record.getMessage() == "graph_rebuild_audit"]
    rejected_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_rejected"
    ]
    failed_records = [record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_failed"]

    assert len(rejected_records) >= 1
    assert len(failed_records) == 0


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
        graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

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


async def test_rebuild_contention_maps_to_429_without_failed_lifecycle_when_executor_raises_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct contention exceptions should not leave runtime lifecycle in FAILED."""

    async def fake_executor(
        _loop: asyncio.AbstractEventLoop,
        _settings: graph_admin.GraphLifecycleSettings,
        *,
        user_ref: str,
        started_at: float,
    ) -> graph_admin.GraphRebuildResponse:
        raise graph_admin._DistributedLockAcquisitionError("busy")  # pylint: disable=protected-access

    monkeypatch.setattr(graph_admin, "_run_rebuild_in_executor", fake_executor)
    from api.graph_lifecycle import reset_graph  # pylint: disable=import-outside-toplevel

    try:
        with pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="admin", disabled=False))
        assert exc_info.value.status_code == 429
        assert graph_admin.get_runtime_lifecycle_state() == graph_admin.GraphRuntimeLifecycleState.READY
    finally:
        graph_admin.shutdown_rebuild_executor()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access
        reset_graph()


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
        *,
        user_ref: str,
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
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

    audit_records = [record for record in caplog.records if record.getMessage() == "graph_rebuild_audit"]
    succeeded_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_succeeded"
    ]
    failed_records = [record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_failed"]

    assert len(succeeded_records) == 1
    assert len(failed_records) == 0
    assert succeeded_records[0].user_ref == "admin"
    assert succeeded_records[0].status_code == 200


# ---------------------------------------------------------------------------
# Rebuild Job Status Endpoints Tests
# ---------------------------------------------------------------------------


def test_get_rebuild_job_returns_403_for_non_operator(
    non_operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs/{job_id} must reject non-operator users."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    response = non_operator_client.get("/api/graph/rebuild/jobs/test-job-id")
    assert response.status_code == 403
    assert response.json()["detail"] == REBUILD_OPERATOR_FORBIDDEN_DETAIL


def test_list_rebuild_jobs_returns_403_for_non_operator(
    non_operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs must reject non-operator users."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    response = non_operator_client.get("/api/graph/rebuild/jobs")
    assert response.status_code == 403
    assert response.json()["detail"] == REBUILD_OPERATOR_FORBIDDEN_DETAIL


def test_get_rebuild_job_returns_503_when_persistence_not_configured(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs/{job_id} must fail closed when persistence DB not configured."""
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    response = operator_client.get("/api/graph/rebuild/jobs/test-job-id")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_list_rebuild_jobs_returns_503_when_persistence_not_configured(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /jobs must fail closed when persistence DB not configured."""
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    response = operator_client.get("/api/graph/rebuild/jobs")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_get_rebuild_job_returns_404_for_unknown_job(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs/{job_id} must return 404 for unknown job IDs."""
    with _rebuild_jobs_db_context(tmp_path, monkeypatch):
        response = operator_client.get("/api/graph/rebuild/jobs/unknown-job-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Rebuild job not found"


def test_get_rebuild_job_succeeds_for_operator(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs/{job_id} must return bounded job state for operator."""
    from src.data.repository import AssetGraphRepository, session_scope

    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = _create_rebuild_jobs(repo, 1, numbered_sources=False)[0]
            repo.mark_rebuild_job_running(job_id)
            repo.mark_rebuild_job_succeeded(
                job_id,
                node_count=100,
                edge_count=250,
                duration_ms=5000,
            )

        response = operator_client.get(f"/api/graph/rebuild/jobs/{job_id}")

    data = _assert_successful_json_response(response)

    # Verify bounded fields
    assert data["job_id"] == job_id
    assert data["status"] == "succeeded"
    assert data["source"] == "test"
    assert data["requested_by"] == "operator"
    assert data["node_count"] == 100
    assert data["edge_count"] == 250
    assert data["duration_ms"] == 5000
    assert data["failure_category"] is None
    assert data["failure_message"] is None

    # Verify datetime fields are present and serialized
    assert "created_at" in data
    assert "updated_at" in data
    assert "started_at" in data
    assert "completed_at" in data


def test_get_rebuild_job_exposes_sanitized_failure_fields(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs/{job_id} must expose sanitized failure metadata only."""
    from src.data.repository import AssetGraphRepository, session_scope

    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = _create_rebuild_jobs(repo, 1, numbered_sources=False)[0]
            repo.mark_rebuild_job_running(job_id)
            repo.mark_rebuild_job_failed(
                job_id,
                failure_category="database_error",
                failure_message="Connection timeout",
                duration_ms=2000,
            )

        response = operator_client.get(f"/api/graph/rebuild/jobs/{job_id}")

    data = _assert_successful_json_response(response)

    assert data["status"] == "failed"
    assert data["failure_category"] == "database_error"
    assert data["failure_message"] == "Connection timeout"
    assert data["duration_ms"] == 2000

    # Verify no raw exceptions or stack traces
    assert "traceback" not in str(data).lower()
    assert "exception" not in str(data).lower()


def test_list_rebuild_jobs_succeeds_for_operator(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs must return bounded list structure for operator."""
    from src.data.repository import AssetGraphRepository, session_scope

    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            _create_rebuild_jobs(repo, 2)

        response = operator_client.get("/api/graph/rebuild/jobs")

    data = _assert_successful_json_response(response)

    # Verify pagination-ready structure
    assert "jobs" in data
    assert "count" in data
    assert isinstance(data["jobs"], list)
    assert data["count"] == 2
    assert len(data["jobs"]) == 2

    # Verify each job has bounded fields
    for job in data["jobs"]:
        assert "job_id" in job
        assert "status" in job
        assert "requested_by" in job
        assert "created_at" in job


def test_list_rebuild_jobs_returns_newest_first_ordering(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs must return jobs in deterministic newest-first order."""
    from datetime import datetime, timedelta, timezone

    base = datetime.now(timezone.utc)

    from src.data.repository import AssetGraphRepository, session_scope

    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_ids = _create_rebuild_jobs(repo, 3)

            jobs = []
            for job_id in job_ids:
                job = repo.get_rebuild_job(job_id)
                assert job is not None
                jobs.append(job)

            jobs[0].created_at = base
            jobs[1].created_at = base + timedelta(seconds=1)
            jobs[2].created_at = base + timedelta(seconds=2)

            # Explicit commit guarantees the ORM changes persist before the client requests them
            session.commit()

        response = operator_client.get("/api/graph/rebuild/jobs")

    data = _assert_successful_json_response(response)

    # Verify newest-first ordering (reverse creation order)
    returned_ids = [job["job_id"] for job in data["jobs"]]
    assert returned_ids == list(reversed(job_ids))


def test_list_rebuild_jobs_returns_empty_list_when_no_jobs(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GET /jobs must return empty list when no jobs exist."""
    with _rebuild_jobs_db_context(tmp_path, monkeypatch):
        response = operator_client.get("/api/graph/rebuild/jobs")

    data = _assert_successful_json_response(response)

    assert data["jobs"] == []
    assert data["count"] == 0
