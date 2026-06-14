"""Integration tests for rebuild job cancellation."""

# pylint: disable=redefined-outer-name

import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.routers.graph_admin import _heartbeat_keeper
from src.data.db_models import RebuildJobStatus
from src.data.repository import AssetGraphRepository, session_scope
from tests.integration.test_graph_admin_router import _rebuild_jobs_db_context


@pytest.fixture
def operator_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[TestClient, None, None]:
    """Client authenticated as the authorized operator user."""
    # Prevent starlette from reading .env which causes PermissionError in this environment
    monkeypatch.setattr("starlette.config.Config._read_file", lambda self, f, e: {})

    db_path = tmp_path / "test_graph.db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", f"sqlite:///{db_path}")

    from src.data.database import create_engine_from_url, init_db

    engine = create_engine_from_url(f"sqlite:///{db_path}")
    init_db(engine)

    from api.app_factory import create_app

    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    app = create_app()
    from api.auth import User, get_current_active_user

    def active_user() -> User:
        """Provide a mock active admin user."""
        return User(username="admin", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    with TestClient(app) as client:
        yield client


def test_cancel_rebuild_happy_path(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """POST /cancel must transition job to cancel_requested."""
    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        # 1. Create a job
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="admin")
            repo.mark_rebuild_job_running(job_id, execution_id="exec-1")

        # 2. Call cancel endpoint
        response = operator_client.post(f"/api/graph/rebuild/jobs/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["message"] == "Cancellation requested"

        # 3. Verify status in DB
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            assert job is not None
            assert job.status == RebuildJobStatus.CANCEL_REQUESTED
            assert job.cancellation_requested_at is not None


def test_cancel_rebuild_not_found(operator_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """POST /cancel must return 404 for unknown jobs."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", "sqlite:///:memory:")
    response = operator_client.post("/api/graph/rebuild/jobs/non-existent/cancel")
    assert response.status_code == 404


def test_cancel_rebuild_invalid_status(
    operator_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """POST /cancel must return 409 for already finished jobs."""
    with _rebuild_jobs_db_context(tmp_path, monkeypatch) as session_factory:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="admin")
            repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
            repo.mark_rebuild_job_succeeded(job_id, execution_id="exec-1", node_count=1, edge_count=1, duration_ms=1)

        response = operator_client.post(f"/api/graph/rebuild/jobs/{job_id}/cancel")
        assert response.status_code == 409
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
            """Simple stub for DistributedLock."""

            def refresh(self):
                """Return True for lock refresh."""
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
