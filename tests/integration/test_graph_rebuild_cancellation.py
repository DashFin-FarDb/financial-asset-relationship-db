"""Integration tests for rebuild job cancellation."""

# pylint: disable=redefined-outer-name

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.routers.graph_admin import _heartbeat_keeper
from src.data.db_models import RebuildJobStatus
from src.data.repository import AssetGraphRepository, session_scope
from tests.integration.test_graph_admin_router import _rebuild_jobs_db_context


@pytest.fixture
def operator_client_and_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Callable[[], Session]]:
    """Provides a TestClient and session_factory bound to the exact same isolated database."""
    # Prevent starlette from reading .env which causes PermissionError in this environment
    monkeypatch.setattr("starlette.config.Config._read_file", lambda self, f, e: {})

    db_path = tmp_path / "test_graph.db"
    db_url = f"sqlite:///{db_path}"

    # Must use os.environ temporarily to ensure settings resolution picks it up across potential thread/process boundaries 
    # and bypasses any cached lru overrides.
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
    os.environ["ASSET_GRAPH_DATABASE_URL"] = db_url

    from src.data.database import create_engine_from_url, create_session_factory, init_db

    engine = create_engine_from_url(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    from api.app_factory import create_app

    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    app = create_app()
    from api.auth import User, get_current_active_user

    def active_user() -> User:
        return User(username="admin", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user

    # We must explicitly clear the lru cache for settings to pick up our environment variable change
    from src.config.settings import get_settings
    get_settings.cache_clear()

    with TestClient(app) as client:
        yield client, session_factory



def test_cancel_rebuild_happy_path(
    operator_client_and_db: tuple[TestClient, Callable[[], Session]],
):
    """POST /cancel must transition job to cancel_requested."""
    client, session_factory = operator_client_and_db

    # 1. Create a job
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="admin")
        repo.mark_rebuild_job_running(job_id, execution_id="exec-1")

    # 2. Call cancel endpoint
    response = client.post(f"/api/graph/rebuild/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["message"] == "Cancellation requested"

    # 3. Verify status in DB
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job = repo.get_rebuild_job(job_id)
        assert job.status == RebuildJobStatus.CANCEL_REQUESTED
        assert job.cancellation_requested_at is not None


def test_cancel_rebuild_not_found(operator_client_and_db: tuple[TestClient, Callable[[], Session]]):
    """POST /cancel must return 404 for unknown jobs."""
    client, _ = operator_client_and_db
    response = client.post("/api/graph/rebuild/non-existent/cancel")
    assert response.status_code == 404


def test_cancel_rebuild_invalid_status(
    operator_client_and_db: tuple[TestClient, Callable[[], Session]],
):
    """POST /cancel must return 400 for already finished jobs."""
    client, session_factory = operator_client_and_db

    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="admin")
        repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
        repo.mark_rebuild_job_succeeded(job_id, execution_id="exec-1", node_count=1, edge_count=1, duration_ms=1)

    response = client.post(f"/api/graph/rebuild/{job_id}/cancel")
    assert response.status_code == 400
    assert "Cannot transition" in response.json()["detail"]


def test_heartbeat_keeper_detects_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """_heartbeat_keeper must set cancel_event when job is marked cancel_requested."""
    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        execution_id = "exec-1"
        worker_id = "worker-1"

        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="admin")
            repo.mark_rebuild_job_running(job_id, execution_id=execution_id)

        # Mock DistributedLock
        class MockLock:
            def refresh(self):
                return True

        stop_event = threading.Event()
        lock_lost_event = threading.Event()
        cancel_event = threading.Event()

        # Start heartbeat keeper in a thread
        keeper_thread = threading.Thread(
            target=_heartbeat_keeper,
            kwargs={
                "session_factory": session_factory,
                "dist_lock": MockLock(),
                "job_id": job_id,
                "execution_id": execution_id,
                "worker_id": worker_id,
                "stop_event": stop_event,
                "lock_lost_event": lock_lost_event,
                "cancel_event": cancel_event,
                "interval_seconds": 0.1,
            },
        )
        keeper_thread.start()

        try:
            # Verify it's running (no events set)
            time.sleep(0.5)
            assert not lock_lost_event.is_set()
            assert not cancel_event.is_set()

            # Now mark as cancel_requested in DB
            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                repo.mark_rebuild_job_cancel_requested(job_id)

            # Heartbeat keeper should detect it within interval
            assert cancel_event.wait(timeout=5.0)
            assert not lock_lost_event.is_set()

        finally:
            stop_event.set()
            keeper_thread.join(timeout=2.0)
            assert not keeper_thread.is_alive(), "Heartbeat keeper thread failed to terminate"
