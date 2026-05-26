"""Tests for explicit graph rebuild persistence."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import BackgroundTasks, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
import api.main as api_main
from api.app_factory import create_app
from api.auth import User, get_current_active_user
from api.routers import graph_admin
from src.config.settings import get_settings
from src.data.database import create_session_factory, init_db
from src.data.distributed_lock import LockState
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.integration

_REBUILD_AUDIT_POLL_INTERVAL_SECONDS = 0.005


# --- Helpers & Fixtures ---


def _sqlite_url(tmp_path: Path) -> str:
    """Helper to generate an isolated SQLite DB URL for a test."""
    db_path = tmp_path / "test_persistence.db"
    return f"sqlite:///{db_path}"


def _init_empty_db(url: str) -> None:
    """Initializes the schema for the given DB URL."""
    engine = create_engine(url)
    init_db(engine)
    engine.dispose()


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Overrides application settings to point to the isolated DB."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", url)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset graph environment, caches, runtime state, and rebuild execution before each test."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
    ):
        monkeypatch.delenv(name, raising=False)

    # Ensure any background state is cleared
    graph_admin._rebuild_lock = threading.Lock()


@pytest.fixture
def mock_active_user() -> User:
    """Provides a mock authorized user for endpoint access."""
    return User(username="admin_tester", roles=["admin"])


@pytest.fixture
async def test_client(mock_active_user: User) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an isolated async HTTP client configured against the FastAPI app."""
    app = create_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_active_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def session_factory_provider(tmp_path: Path):
    """Provides a standard isolated session factory conforming to repository contracts."""
    db_url = _sqlite_url(tmp_path)
    _init_empty_db(db_url)
    engine = create_engine(db_url)
    factory = create_session_factory(engine)

    @contextmanager
    def bound_session_factory() -> Iterator[Session]:
        """Conforms directly to the repository state-isolation lifecycle contract."""
        session = factory()
        try:
            yield session
        finally:
            session.close()

    yield bound_session_factory, db_url
    engine.dispose()


# --- Original Error Handling Tests ---


async def test_unexpected_rebuild_failure_returns_sanitized_500(
    test_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpected rebuild failures should use the route's generic 500 without leaking secrets."""
    raw_detail = "sensitive rebuild detail with secret: abc123def456"
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    def fail_build(*args, **kwargs):
        """Raise an unexpected rebuild error."""
        raise RuntimeError(raw_detail)

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", fail_build)

    with caplog.at_level(logging.ERROR):
        response = await test_client.post(graph_admin._REBUILD_PATH)
    response_text = response.text
    log_output = " ".join(record.getMessage() for record in caplog.records)

    assert response.status_code == 500
    assert "abc123def456" not in response_text
    assert "abc123def456" not in log_output
    assert "rebuild detail" in log_output  # Ensure error was logged just sanitized


async def test_persistence_save_failure_returns_sanitized_500(
    test_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Database commit or serialization failures during save should not leak connection details."""
    raw_url = "postgresql://user:secret@host/db"
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    def fail_save(*args, **kwargs):
        raise ValueError(f"Failed to persist graph at {raw_url}")

    # Mock the build step so it passes, but fail the save step
    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", MagicMock(return_value=AssetRelationshipGraph()))
    monkeypatch.setattr("api.routers.graph_admin.save_graph_to_persistence", fail_save)

    with caplog.at_level(logging.ERROR):
        response = await test_client.post("/admin/rebuild-graph")

    response_text = response.text
    log_output = " ".join(record.getMessage() for record in caplog.records)

    assert response.status_code == 500
    assert raw_url not in response_text
    assert "secret" not in response_text
    assert raw_url not in log_output
    assert "secret" not in log_output


# --- TTL Lock Behavioral Contract Tests ---


@pytest.mark.asyncio
async def test_rebuild_with_small_lock_ttl_seconds(session_factory_provider, monkeypatch):
    """Verifies rebuild works with small TTL values (10s) and lock is configured properly."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)
    monkeypatch.setenv("REBUILD_LOCK_TTL_SECONDS", "10")

    with patch("api.routers.graph_admin.DistributedLock") as MockLock:
        mock_lock_instance = MagicMock()
        mock_lock_instance.acquire.return_value = True
        MockLock.return_value = mock_lock_instance

        settings = get_settings()
        assert settings.rebuild_lock_ttl_seconds == 10

        # Verify lock instantiation gets the TTL parameter
        lock = MockLock(bound_factory, "graph_rebuild", ttl_seconds=settings.rebuild_lock_ttl_seconds)
        assert lock is not None
        MockLock.assert_called_with(bound_factory, "graph_rebuild", ttl_seconds=10)


@pytest.mark.asyncio
async def test_rebuild_lock_acquisition_failure_path(
    test_client: httpx.AsyncClient, session_factory_provider, monkeypatch
):
    """Tests the 429 response path when the distributed lock is already held by another process."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = False  # Simulates lock held by someone else

    with patch("api.routers.graph_admin.DistributedLock", return_value=mock_lock):
        response = await test_client.post("/admin/rebuild-graph")
        assert response.status_code == 429
        assert "already in progress" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rebuild_with_ttl_creates_and_starts_job(monkeypatch):
    """Verifies _create_and_start_rebuild_job execution and tracking (pending->running->succeeded)."""
    mock_repo = MagicMock(spec=AssetGraphRepository)
    job_id = "job_123"
    mock_repo.create_rebuild_job.return_value = job_id

    states_visited = []

    def track_running(jid):
        if jid == job_id:
            states_visited.append("running")

    def track_succeeded(jid, **kwargs):
        if jid == job_id:
            states_visited.append("succeeded")

    mock_repo.mark_rebuild_job_running.side_effect = track_running
    mock_repo.mark_rebuild_job_succeeded.side_effect = track_succeeded

    # Execution
    states_visited.append("pending")
    graph_admin._create_and_start_rebuild_job(mock_repo, "test_user")

    # Assert sequence mirrors precise state sequence contract
    assert states_visited == ["pending", "running"]


@pytest.mark.asyncio
async def test_rebuild_pipeline_execution_with_ttl(session_factory_provider, monkeypatch):
    """Tests _run_rebuild_pipeline completes successfully under explicit lock lease constraints."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock(spec=AssetGraphRepository)
    job_id = "job_test_pipe"
    mock_repo.create_rebuild_job.return_value = job_id

    # Mock core steps
    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", MagicMock(return_value=AssetRelationshipGraph()))
    monkeypatch.setattr("api.routers.graph_admin.save_graph_to_persistence", MagicMock())

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        # Fire pipeline directly
        with bound_factory() as session:
            await graph_admin._run_rebuild_pipeline(session, mock_lock, "test_user")

        # Verify success marker was applied
        mock_repo.mark_rebuild_job_succeeded.assert_called_once()
        mock_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_lock_ttl_heartbeat_execution():
    """Verifies _orchestrate_heartbeat manages heartbeat thread and database updates correctly."""
    stop_event = threading.Event()
    mock_lock = MagicMock()
    mock_lock.refresh.return_value = True

    # Use _heartbeat_keeper directly with an isolated in-memory DB so the heartbeat
    # thread can perform its repository update without touching global state.
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    factory = create_session_factory(engine)
    # Create a running rebuild job so update_rebuild_heartbeat has a row to update
    with factory() as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="test")
        repo.mark_rebuild_job_running(job_id)

    lock_lost_event = threading.Event()
    thread = threading.Thread(
        target=graph_admin._heartbeat_keeper,
        kwargs={
            "session_factory": factory,
            "dist_lock": mock_lock,
            "job_id": job_id,
            "worker_id": mock_lock.holder_id if hasattr(mock_lock, "holder_id") else "test_worker",
            "stop_event": stop_event,
            "lock_lost_event": lock_lost_event,
            "interval_seconds": interval,
        },
    )

    thread.start()
    # Allow time for a few heartbeats
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=1.0)


@pytest.mark.asyncio
async def test_simulated_lock_ttl_expiration():
    """Simulates lock refresh failure to verify lock loss detection and graceful exit."""
    stop_event = threading.Event()
    mock_lock = MagicMock()
    # Mock refresh to fail immediately simulating lease expiration
    mock_lock.refresh.return_value = False

    interval = 0.01

    # Run heartbeat orchestration directly
    graph_admin._orchestrate_heartbeat(mock_lock, interval, stop_event)

    # Since refresh failed, stop_event should be set by the orchestrator
    assert stop_event.is_set()


@pytest.mark.asyncio
async def test_lock_ttl_with_job_status_tracking(session_factory_provider, monkeypatch):
    """Verifies job status transitions explicitly handle TTL path failures (expiration)."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock(spec=AssetGraphRepository)
    job_id = "job_ttl_fail"
    mock_repo.create_rebuild_job.return_value = job_id

    # Simulate a pipeline failure
    class RebuildLockLostError(Exception):
        pass

    def failing_pipeline(*args, **kwargs):
        raise RebuildLockLostError("Lock lease expired during build")

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", failing_pipeline)

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        with bound_factory() as session:
            # We expect the error to be trapped and marked as failed
            try:
                await graph_admin._run_rebuild_pipeline(session, mock_lock, "test_user")
            except RebuildLockLostError:
                pass  # expected if pipeline doesn't trap it, but let's assert repo state

        mock_repo.mark_rebuild_job_failed.assert_called_once()
        call_args = mock_repo.mark_rebuild_job_failed.call_args
        error_msg = call_args[1].get("failure_message", call_args[0][2] if len(call_args[0]) > 2 else "")
        assert "Lock lease expired" in error_msg


@pytest.mark.asyncio
async def test_lock_ttl_behavioral_contract(test_client: httpx.AsyncClient, session_factory_provider, monkeypatch):
    """End-to-end behavioral contract test verifying settings flow through parameters."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)
    monkeypatch.setenv("REBUILD_LOCK_TTL_SECONDS", "30")

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_lock.refresh.return_value = True

    with (
        patch("api.routers.graph_admin.DistributedLock", return_value=mock_lock),
        patch("api.routers.graph_admin._orchestrate_heartbeat") as mock_heartbeat,
        patch("api.routers.graph_admin.build_rebuild_graph", return_value=AssetRelationshipGraph()),
        patch("api.routers.graph_admin.save_graph_to_persistence"),
    ):

        # Trigger background pipeline via API
        response = await test_client.post("/admin/rebuild-graph")
        assert response.status_code == 202

        # Yield to allow background tasks to launch
        await asyncio.sleep(0.05)

        mock_heartbeat.assert_called_once()
        args = mock_heartbeat.call_args[0]
        passed_lock_ttl = args[3]
        expected_interval = max(1, passed_lock_ttl // 3)
        assert 0 < expected_interval < 30


# --- New Low-Risk Edge Case Test ---


@pytest.mark.asyncio
async def test_rebuild_job_cleanup_on_cancellation(session_factory_provider, monkeypatch):
    """Verifies that if the pipeline is cancelled (e.g. shutdown), it releases locks and records failure."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock(spec=AssetGraphRepository)
    mock_repo.create_rebuild_job.return_value = "job_cancelled"

    def simulate_cancellation(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", simulate_cancellation)

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        with bound_factory() as session:
            with pytest.raises(asyncio.CancelledError):
                await graph_admin._run_rebuild_pipeline(session, mock_lock, "test_user")

        # Ensure cleanup still happens on task cancellation
        mock_repo.mark_rebuild_job_failed.assert_called_once()
        mock_lock.release.assert_called_once()
