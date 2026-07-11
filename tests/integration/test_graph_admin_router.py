"""Tests for graph admin router registration."""

# pylint: disable=redefined-outer-name

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Generator, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException  # pylint: disable=import-error
from fastapi.testclient import TestClient  # pylint: disable=import-error

# Module-level import is safe as api.routers.graph_admin is side-effect free on import.
# This allows direct access to internal helpers for tests and ensuring monkeypatch targets are available.
import api.routers.graph_admin as graph_admin
from api.auth import (
    REBUILD_OPERATOR_FORBIDDEN_DETAIL,
    REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL,
    User,
    get_current_active_user,
)
from api.graph_lifecycle import reset_graph
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.repository import AssetGraphRepository, RebuildFailureDetails, session_scope

pytestmark = pytest.mark.integration

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


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


@pytest.fixture(autouse=True)
def _reset_graph_lifecycle_state() -> Iterator[None]:
    """Keep global graph runtime lifecycle isolated across tests."""
    reset_graph()
    try:
        yield
    finally:
        reset_graph()


def _assert_successful_json_response(response: httpx.Response) -> dict[str, Any]:
    """Assert response is 200 OK and return the parsed JSON."""
    assert response.status_code == 200
    return response.json()


@contextlib.contextmanager
def _rebuild_jobs_db_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    """Provide a clean, initialized database and session factory for tests."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    settings = get_settings()
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


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure the expected admin username is set via env vars and clear cache."""
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_app_construction_with_graph_admin_router_succeeds() -> None:
    """The graph admin router must not introduce an app construction import cycle."""
    from api.app_factory import create_app  # pylint: disable=import-outside-toplevel

    app = create_app()
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
        execution_id: str,
    ) -> graph_admin.GraphRebuildResponse:
        """Return a mock successful GraphRebuildResponse."""
        _ = user_ref
        _ = execution_id
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
        graph_admin.shutdown_rebuild_executor_sync()
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
        execution_id: str,
    ) -> graph_admin.GraphRebuildResponse:
        """Fake rebuild implementation that raises a lock acquisition error."""
        _ = user_ref
        _ = execution_id
        raise graph_admin._DistributedLockAcquisitionError("busy")  # pylint: disable=protected-access

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", fake_rebuild)

    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"):
            response = operator_client.post("/api/graph/rebuild")
    finally:
        graph_admin.shutdown_rebuild_executor_sync()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

    assert response.status_code == 429
    assert graph_admin.get_runtime_lifecycle_state() == graph_admin.GraphRuntimeLifecycleState.READY

    audit_records = [record for record in caplog.records if getattr(record, "event", "").startswith("graph_rebuild_")]
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
    mock_settings: Any,
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

    audit_records = [record for record in caplog.records if getattr(record, "event", "").startswith("graph_rebuild_")]
    requested_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_requested"
    ]
    rejected_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_rejected"
    ]

    assert len(requested_records) == 1
    assert len(rejected_records) == 1
    req_meta = cast(dict[str, Any], getattr(requested_records[0], "metadata", {}))
    rej_meta = cast(dict[str, Any], getattr(rejected_records[0], "metadata", {}))
    assert req_meta["user_ref"] == "admin"
    assert req_meta["path"] == "/api/graph/rebuild"
    assert rej_meta["reason"] == "rebuild_in_progress"
    assert rej_meta["status_code"] == 429


async def test_rebuild_contention_maps_to_429_without_failed_lifecycle_when_executor_raises_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lock contention maps to HTTP 429 when executor raises error directly.

    Verifies that when the rebuild executor raises a distributed-lock acquisition error directly,
    the request maps to HTTP 429 and the runtime lifecycle remains READY.
    """

    async def _fake_executor_acquisition_error(*_args, **_kwargs):
        """Fake executor that raises a lock acquisition error."""
        raise graph_admin._DistributedLockAcquisitionError("busy")  # pylint: disable=protected-access

    monkeypatch.setattr(graph_admin, "_run_rebuild_in_executor", _fake_executor_acquisition_error)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="admin", disabled=False))
        assert exc_info.value.status_code == 429
        assert graph_admin.get_runtime_lifecycle_state() == graph_admin.GraphRuntimeLifecycleState.READY
    finally:
        graph_admin.shutdown_rebuild_executor_sync()
        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access
        reset_graph()


async def test_rebuild_lock_lost_maps_to_503_when_executor_raises_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lock-loss exceptions should map to HTTP 503 with failed lifecycle state."""
    reset_graph()
    if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
        graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)  # pylint: disable=protected-access

    async def _fake_executor_lock_lost_error(*_args, **_kwargs):
        """Fake executor that raises a lock lost error."""
        raise graph_admin._DistributedLockLostError("lost")  # pylint: disable=protected-access

    monkeypatch.setattr(graph_admin, "_run_rebuild_in_executor", _fake_executor_lock_lost_error)

    try:
        with pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="admin", disabled=False))

        assert exc_info.value.status_code == 503

        # Verify structured dictionary contract fields
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail["code"] == "distributed_lock_lost_during_rebuild"
            assert detail["message"] == "Distributed lock lost during rebuild."
        else:
            assert detail == "Distributed lock lost during rebuild."

        assert graph_admin.get_runtime_lifecycle_state() == graph_admin.GraphRuntimeLifecycleState.FAILED

    finally:
        try:
            graph_admin.shutdown_rebuild_executor_sync()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging.getLogger("api.routers.graph_admin").debug(
                "Suppressed non-fatal exception during test executor shutdown teardown: %s", exc
            )

        if graph_admin._REBUILD_RUNTIME.is_busy():  # pylint: disable=protected-access
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=False)  # pylint: disable=protected-access
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


async def test_rebuild_outcome_logging_survives_request_cancellation_hardened(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    mock_settings: Any,
) -> None:
    """Callback logs outcome metrics layout correctly when task context cancellation occurs."""
    thread_reached = threading.Event()
    proceed_thread = threading.Event()
    callback_completed = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Track logging directly so we only finish when the thread genuinely concludes
    original_log = graph_admin._log_rebuild_succeeded  # noqa: F841

    def track_log(*args, **kwargs):
        """Wrap the log execution to track when a success log event is emitted."""
        try:
            return original_log(*args, **kwargs)
        finally:
            loop.call_soon_threadsafe(callback_completed.set)

    monkeypatch.setattr(graph_admin, "_log_rebuild_succeeded", track_log)

    def coordinated_sync_rebuild(*_args, **_kwargs):
        """Coordinated rebuild that waits for a signal before proceeding."""
        thread_reached.set()
        proceed_thread.wait(timeout=5.0)
        return graph_admin.GraphRebuildResponse(
            status="persisted", source="sample", asset_count=5, relationship_count=2, regulatory_event_count=0
        )

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", coordinated_sync_rebuild)

    if graph_admin._REBUILD_RUNTIME.is_busy():
        graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)
    graph_admin._REBUILD_RUNTIME.mark_busy()

    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"):
            task = asyncio.create_task(
                graph_admin._run_rebuild_in_executor(
                    loop,
                    graph_admin.get_graph_lifecycle_settings(),
                    user_ref="admin",
                    started_at=time.perf_counter(),
                    tracking_state={"audit_logged": False},
                )
            )

            await loop.run_in_executor(None, thread_reached.wait)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            proceed_thread.set()
            await asyncio.wait_for(callback_completed.wait(), timeout=3.0)

    finally:
        graph_admin.shutdown_rebuild_executor_sync()
        if graph_admin._REBUILD_RUNTIME.is_busy():
            graph_admin._REBUILD_RUNTIME.mark_idle(succeeded=True)
        reset_graph()

    audit_records = [record for record in caplog.records if getattr(record, "event", "").startswith("graph_rebuild_")]
    succeeded_records = [
        record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_succeeded"
    ]
    failed_records = [record for record in audit_records if getattr(record, "event", None) == "graph_rebuild_failed"]

    assert len(succeeded_records) == 1
    assert len(failed_records) == 0
    succ_meta = cast(dict[str, Any], getattr(succeeded_records[0], "metadata", {}))
    assert succ_meta["user_ref"] == "admin"
    assert succ_meta["status_code"] == 200


async def test_rebuild_unexpected_programming_error_emits_sentinel_and_audits(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raw programming error must emit an unexpected sentinel and exactly one audit log."""

    async def fake_executor_bug(*args, **kwargs):
        """Fake executor that simulates a programming bug."""
        # Simulate a programming bug (e.g. referencing a missing attribute)
        raise AttributeError("NoneType object has no attribute 'assets'")

    monkeypatch.setattr(graph_admin, "_run_rebuild_in_executor", fake_executor_bug)

    try:
        with caplog.at_level(logging.INFO, logger="api.routers.graph_admin"), pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(User(username="admin", disabled=False))

        assert exc_info.value.status_code == 500

        # Verify the explicit sentinel alert log was captured
        sentinel_logs = [r for r in caplog.records if getattr(r, "event", None) == "graph_rebuild_unexpected_exception"]
        assert len(sentinel_logs) == 1
        assert sentinel_logs[0].levelname == "CRITICAL"
        sent_meta = cast(dict[str, Any], getattr(sentinel_logs[0], "metadata", {}))
        assert sent_meta["exception_type"] == "AttributeError"

        # Verify exactly one failure audit event log was broadcast
        audit_logs = [r for r in caplog.records if getattr(r, "event", "").startswith("graph_rebuild_")]
        failed_audits = [r for r in audit_logs if getattr(r, "event", None) == "graph_rebuild_failed"]
        assert len(failed_audits) == 1
        fail_meta = cast(dict[str, Any], getattr(failed_audits[0], "metadata", {}))
        assert fail_meta["failure_category"] == "unexpected_error"

    finally:
        graph_admin.shutdown_rebuild_executor_sync()


# ---------------------------------------------------------------------------
# Rebuild Job Status Endpoints Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/graph/rebuild/jobs/test-job-id",
        "/api/graph/rebuild/jobs",
    ],
)
def test_rebuild_jobs_endpoints_return_403_for_non_operator(
    non_operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """GET /jobs/{job_id} and GET /jobs must reject non-operator users."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()
    response = non_operator_client.get(path)
    assert response.status_code == 403
    assert response.json()["detail"] == REBUILD_OPERATOR_FORBIDDEN_DETAIL


@pytest.mark.parametrize(
    "path",
    [
        "/api/graph/rebuild/jobs/test-job-id",
        "/api/graph/rebuild/jobs",
    ],
)
def test_rebuild_jobs_endpoints_return_503_when_persistence_not_configured(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """GET /jobs/{job_id} and GET /jobs must fail closed when persistence DB not configured."""
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    response = operator_client.get(path)
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
    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = _create_rebuild_jobs(repo, 1, numbered_sources=False)[0]
            execution_id = "test-exec-id"
            repo.mark_rebuild_job_running(job_id, execution_id)
            repo.mark_rebuild_job_succeeded(
                job_id,
                execution_id=execution_id,
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
    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = _create_rebuild_jobs(repo, 1, numbered_sources=False)[0]
            execution_id = "test-exec-id"
            repo.mark_rebuild_job_running(job_id, execution_id)
            repo.mark_rebuild_job_failed(
                job_id,
                execution_id=execution_id,
                details=RebuildFailureDetails(
                    failure_category="database_error", failure_message="Connection timeout", duration_ms=2000
                ),
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
    base = datetime.now(timezone.utc)  # noqa: UP017

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
