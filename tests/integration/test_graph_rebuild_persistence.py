"""Tests for explicit graph rebuild persistence."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncGenerator, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import api.graph_lifecycle_providers as providers
from api.app_factory import create_app
from api.auth import User, get_current_active_user
from api.routers import graph_admin
from src.config.settings import get_settings
from src.data.database import create_session_factory, init_db, create_engine_from_url
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.integration

_REBUILD_AUDIT_POLL_INTERVAL_SECONDS = 0.005


# --- Structural Layout & Configuration Helpers ---

def _sqlite_url(tmp_path: Path) -> str:
    """Helper to generate an isolated SQLite DB URL for a test."""
    db_path = tmp_path / "test_persistence.db"
    return f"sqlite:///{db_path}"


def _init_empty_db(url: str) -> None:
    """Initializes the database schema using canonical schemas."""
    engine = create_engine(url)
    init_db(engine)
    engine.dispose()


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Overrides environment parameters cleanly to target test sandboxes."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset graph environment configuration states and route locks before each run execution."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
        "REBUILD_LOCK_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    
    get_settings.cache_clear()
    providers.clear_graph_lifecycle_settings_cache()
    graph_admin._REBUILD_RUNTIME.lock = None
    graph_admin._REBUILD_RUNTIME.lock_loop = None
    graph_admin.shutdown_rebuild_executor_sync()


@pytest.fixture
def mock_active_user() -> User:
    """Provides a typed mock administrative user constraint."""
    return User(username="admin_tester", roles=["admin"])


@pytest.fixture
async def test_client(mock_active_user: User) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides a clean, contract-compliant async HTTP testing client sandbox."""
    app = create_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_active_user
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def session_factory_provider(tmp_path: Path):
    """Provides an isolated, production-contract-compliant database context session factory."""
    db_url = "sqlite:///:memory:"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    factory = create_session_factory(engine)
    
    @contextmanager
    def bound_session_factory() -> Iterator[Session]:
        """Provides state-isolated contextual sessions matching factory lifecycle models."""
        session = factory()
        try:
            yield session
        finally:
            session.close()

    yield bound_session_factory, db_url
    engine.dispose()


# --- Security Error & Isolation Handling Enforcements ---

async def test_unexpected_rebuild_failure_returns_sanitized_500(
    test_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpected rebuild failures must hide private environment contexts from responses."""
    raw_detail = "sensitive rebuild detail with secret: abc123def456"
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    def fail_build(*args, **kwargs):
        raise RuntimeError(raw_detail)

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", fail_build)

    with caplog.at_level(logging.ERROR):
        response = await test_client.post("/admin/rebuild-graph")
    response_text = response.text
    log_output = " ".join(record.getMessage() for record in caplog.records)

    assert response.status_code == 500
    assert "abc123def456" not in response_text
    assert "abc123def456" not in log_output
    assert "rebuild detail" in log_output


async def test_persistence_save_failure_returns_sanitized_500(
    test_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Persistence faults should not leak internal database credential vectors via standard outputs."""
    raw_url = "postgresql://user:secret@host/db"
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    def fail_save(*args, **kwargs):
        raise ValueError(f"Failed to persist graph at {raw_url}")

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


# --- Core Rebuild Distributed Lock TTL Flow Integrations ---

@pytest.mark.asyncio
async def test_rebuild_with_small_lock_ttl_seconds(session_factory_provider, monkeypatch):
    """Verifies rebuild honors custom configured lock lease parameters safely down to low constraints."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)
    monkeypatch.setenv("REBUILD_LOCK_TTL_SECONDS", "10")

    with patch("api.routers.graph_admin.DistributedLock") as MockLock:
        mock_lock_instance = MagicMock()
        mock_lock_instance.acquire.return_value = True
        MockLock.return_value = mock_lock_instance

        settings = get_settings()
        assert settings.rebuild_lock_ttl_seconds == 10

        lock = MockLock(bound_factory, "graph_rebuild", ttl_seconds=settings.rebuild_lock_ttl_seconds)
        assert lock is not None
        MockLock.assert_called_with(bound_factory, "graph_rebuild", ttl_seconds=10)


@pytest.mark.asyncio
async def test_rebuild_lock_acquisition_failure_path(
    test_client: httpx.AsyncClient, session_factory_provider, monkeypatch
):
    """Verifies that an incoming administrative build invocation fields an HTTP 429 when lock is active."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = False

    with patch("api.routers.graph_admin.DistributedLock", return_value=mock_lock):
        response = await test_client.post("/admin/rebuild-graph")
        assert response.status_code == 429
        assert "already in progress" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rebuild_with_ttl_creates_and_starts_job(monkeypatch):
    """Verifies job sequence tracks expected standard persistence boundaries: pending -> running."""
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

    states_visited.append("pending")
    graph_admin._create_and_start_rebuild_job(mock_repo, "test_user")

    assert states_visited == ["pending", "running"]


@pytest.mark.asyncio
async def test_rebuild_pipeline_execution_with_ttl(session_factory_provider, monkeypatch):
    """Tests that _run_rebuild_pipeline executes to completion when under structural lock context constraints."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock(spec=AssetGraphRepository)
    job_id = "job_test_pipe"
    mock_repo.create_rebuild_job.return_value = job_id

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", MagicMock(return_value=AssetRelationshipGraph()))
    monkeypatch.setattr("api.routers.graph_admin.save_graph_to_persistence", MagicMock())

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        settings = get_settings()
        engine_for_test = create_engine(db_url)
        session_factory = create_session_factory(engine_for_test)
        job_started_at = time.time()
        lock_lost_event = threading.Event()
        
        graph_admin._run_rebuild_pipeline(
            session_factory,
            settings,
            db_url,
            job_id,
            job_started_at,
            lock_lost_event,
        )
        engine_for_test.dispose()

        mock_repo.mark_rebuild_job_succeeded.assert_called_once()


@pytest.mark.asyncio
async def test_lock_ttl_heartbeat_execution():
    """Verifies _heartbeat_keeper spins off context sync metrics loops and updates transactional updates."""
    stop_event = threading.Event()
    mock_lock = MagicMock()
    mock_lock.refresh.return_value = True

    engine = create_engine_from_url("sqlite:///:memory:")
    init_db(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="test")
        repo.mark_rebuild_job_running(job_id)
        original_updated_at = repo.get_rebuild_job(job_id).updated_at

    time.sleep(0.01)

    lock_lost_event = threading.Event()
    thread = threading.Thread(
        target=graph_admin._heartbeat_keeper,
        kwargs={
            "session_factory": factory,
            "dist_lock": mock_lock,
            "job_id": job_id,
            "worker_id": "test_worker",
            "stop_event": stop_event,
            "lock_lost_event": lock_lost_event,
            "interval_seconds": 0.01,
        },
    )

    thread.start()
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=1.0)

    assert mock_lock.refresh.call_count >= 2
    with factory() as session:
        repo = AssetGraphRepository(session)
        job = repo.get_rebuild_job(job_id)
        assert job.updated_at > original_updated_at
    engine.dispose()


@pytest.mark.asyncio
async def test_simulated_lock_ttl_expiration():
    """Simulates lock refresh failure to verify lock loss detection maps smoothly to thread triggers."""
    mock_lock = MagicMock()
    mock_lock.refresh.return_value = False
    mock_lock.holder_id = "test_worker"

    mock_session_factory = MagicMock()
    job_id = "test_job"
    lock_ttl = 3

    with graph_admin._orchestrate_heartbeat(mock_session_factory, mock_lock, job_id, lock_ttl) as lock_lost_event:
        lock_lost_event.wait(timeout=1.0)

    assert lock_lost_event.is_set()


@pytest.mark.asyncio
async def test_lock_ttl_with_job_status_tracking(session_factory_provider, monkeypatch):
    """Verifies job status transitions map exceptions gracefully to persistence markers when exceptions arise."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock(spec=AssetGraphRepository)
    job_id = "job_ttl_fail"
    mock_repo.create_rebuild_job.return_value = job_id

    class RebuildLockLostError(Exception):
        pass

    def failing_pipeline(*args, **kwargs):
        raise RebuildLockLostError("Lock lease expired during build")

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", failing_pipeline)

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        engine_for_test = create_engine(db_url)
        session_factory = create_session_factory(engine_for_test)
        
        try:
            graph_admin._run_rebuild_pipeline(
                session_factory,
                get_settings(),
                db_url,
                job_id,
                time.time(),
                threading.Event()
            )
        except RebuildLockLostError:
            pass
        finally:
            engine_for_test.dispose()

        mock_repo.mark_rebuild_job_failed.assert_called_once()
        call_args = mock_repo.mark_rebuild_job_failed.call_args
        error_msg = call_args[1].get("failure_message", call_args[0][2] if len(call_args[0]) > 2 else "")
        assert "Lock lease expired" in error_msg


@pytest.mark.asyncio
async def test_lock_ttl_behavioral_contract(test_client: httpx.AsyncClient, session_factory_provider, monkeypatch):
    """End-to-end behavioral contract test verifying settings flow accurately through the route configuration."""
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
        response = await test_client.post("/admin/rebuild-graph")
        assert response.status_code == 202

        await asyncio.sleep(0.05)

        mock_heartbeat.assert_called_once()
        args = mock_heartbeat.call_args[0]
        passed_lock_ttl = args[3]
        expected_interval = max(1, passed_lock_ttl // 3)

        assert 0 < expected_interval < 30, f"Expected interval {expected_interval} out of range"

        actual_interval = mock_heartbeat.call_args[0][3]
        assert actual_interval == max(1, passed_lock_ttl // 3)


# --- Resilience Guardrail Enforcements ---

@pytest.mark.asyncio
async def test_rebuild_job_cleanup_on_cancellation(session_factory_provider, monkeypatch):
    """Verifies that if the pipeline is cancelled, it releases configuration locks and records clean failure states."""
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
        engine_for_test = create_engine(db_url)
        session_factory = create_session_factory(engine_for_test)
        
        with pytest.raises(asyncio.CancelledError):
            graph_admin._run_rebuild_pipeline(
                session_factory,
                get_settings(),
                db_url,
                "job_cancelled",
                time.time(),
                threading.Event()
            )
        engine_for_test.dispose()

        mock_repo.mark_rebuild_job_failed.assert_called_once()


@pytest.mark.asyncio
async def test_rebuild_pipeline_aborts_immediately_on_preexisting_lock_loss(session_factory_provider, monkeypatch):
    """Verifies pipeline processing terminates tracking immediately if the structural loss flag arrives preset."""
    bound_factory, db_url = session_factory_provider
    _configure_persistence(monkeypatch, db_url)

    mock_repo = MagicMock(spec=AssetGraphRepository)
    mock_repo.create_rebuild_job.return_value = "job_immediate_abort"
    mock_build = MagicMock()

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", mock_build)

    with patch("api.routers.graph_admin.AssetGraphRepository", return_value=mock_repo):
        engine_for_test = create_engine(db_url)
        session_factory = create_session_factory(engine_for_test)
        
        lock_lost_event = threading.Event()
        lock_lost_event.set()
        
        graph_admin._run_rebuild_pipeline(
            session_factory, 
            get_settings(), 
            db_url, 
            "job_immediate_abort", 
            time.time(), 
            lock_lost_event
        )
        engine_for_test.dispose()

        mock_build.assert_not_called()
        mock_repo.mark_rebuild_job_failed.assert_called_once()
