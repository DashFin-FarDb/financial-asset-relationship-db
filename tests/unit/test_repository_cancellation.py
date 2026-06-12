"""Unit tests for rebuild job cancellation repository methods."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.db_models import Base, RebuildJobORM, RebuildJobStatus
from src.data.repository import AssetGraphRepository, RebuildCancellationRequestedError


@pytest.fixture
def repo(tmp_path: Path) -> AssetGraphRepository:
    """Fixture providing an AssetGraphRepository with an initialized SQLite database."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    return AssetGraphRepository(session)


def test_mark_rebuild_job_cancel_requested_transitions_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancel_requested must update status and cancellation timestamp."""
    job_id = repo.create_rebuild_job(requested_by="user")

    repo.mark_rebuild_job_cancel_requested(job_id)

    job = repo.get_rebuild_job(job_id)
    assert job.status == RebuildJobStatus.CANCEL_REQUESTED
    assert job.cancellation_requested_at is not None
    assert isinstance(job.cancellation_requested_at, datetime)


def test_mark_rebuild_job_cancel_requested_fails_for_terminal_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancel_requested must fail if job is already succeeded or failed."""
    job_id = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
    repo.mark_rebuild_job_succeeded(job_id, execution_id="exec-1", node_count=1, edge_count=1, duration_ms=1)

    with pytest.raises(ValueError, match="Cannot transition job .* to cancel_requested"):
        repo.mark_rebuild_job_cancel_requested(job_id)


def test_mark_rebuild_job_cancelled_finalizes_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancelled must move from cancel_requested to cancelled."""
    job_id = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
    repo.mark_rebuild_job_cancel_requested(job_id)

    repo.mark_rebuild_job_cancelled(job_id, execution_id="exec-1")

    job = repo.get_rebuild_job(job_id)
    assert job.status == RebuildJobStatus.CANCELLED
    assert job.completed_at is not None


def test_mark_rebuild_job_cancelled_enforces_execution_identity(repo: AssetGraphRepository):
    """mark_rebuild_job_cancelled must fail if execution_id does not match."""
    job_id = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
    repo.mark_rebuild_job_cancel_requested(job_id)

    with pytest.raises(ValueError, match="Execution identity mismatch"):
        repo.mark_rebuild_job_cancelled(job_id, execution_id="wrong-exec")


def test_update_rebuild_heartbeat_raises_cancellation_requested_error(repo: AssetGraphRepository):
    """update_rebuild_heartbeat must raise RebuildCancellationRequestedError if status is cancel_requested."""
    job_id = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
    repo.mark_rebuild_job_cancel_requested(job_id)

    with pytest.raises(RebuildCancellationRequestedError, match="cancellation has been requested"):
        repo.update_rebuild_heartbeat(job_id, execution_id="exec-1", worker_id="worker-1")
