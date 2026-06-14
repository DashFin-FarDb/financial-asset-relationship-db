"""Unit tests for rebuild job cancellation repository methods."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.db_models import Base, RebuildJobStatus
from src.data.repository import AssetGraphRepository, RebuildCancellationRequestedError


@pytest.fixture
def repo(tmp_path: Path) -> Generator[AssetGraphRepository, None, None]:
    """Fixture providing an AssetGraphRepository with an initialized SQLite database."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield AssetGraphRepository(session)
    finally:
        session.close()
        engine.dispose()


def test_mark_rebuild_job_cancel_requested_transitions_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancel_requested must update status and cancellation timestamp."""
    job_id = repo.create_rebuild_job(requested_by="user")

    repo.mark_rebuild_job_cancel_requested(job_id)

    job = repo.get_rebuild_job(job_id)
    assert job is not None
    assert job.status == RebuildJobStatus.CANCEL_REQUESTED
    assert job.cancellation_requested_at is not None
    assert isinstance(job.cancellation_requested_at, datetime)


def test_mark_rebuild_job_cancel_requested_fails_for_terminal_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancel_requested must fail if job is already succeeded or failed."""
    # Test Succeeded
    job_id_succ = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id_succ, execution_id="exec-succ")
    repo.mark_rebuild_job_succeeded(job_id_succ, execution_id="exec-succ", node_count=1, edge_count=1, duration_ms=1)

    with pytest.raises(ValueError, match="Cannot transition job .* to cancel_requested"):
        repo.mark_rebuild_job_cancel_requested(job_id_succ)

    # Test Failed
    job_id_fail = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id_fail, execution_id="exec-fail")
    repo.mark_rebuild_job_failed(
        job_id_fail,
        execution_id="exec-fail",
        failure_category="unexpected_error",
        failure_message="oops",
        duration_ms=100,
    )

    with pytest.raises(ValueError, match="Cannot transition job .* to cancel_requested"):
        repo.mark_rebuild_job_cancel_requested(job_id_fail)


def test_mark_rebuild_job_cancelled_finalizes_status(repo: AssetGraphRepository):
    """mark_rebuild_job_cancelled must move from cancel_requested to cancelled."""
    job_id = repo.create_rebuild_job(requested_by="user")
    repo.mark_rebuild_job_running(job_id, execution_id="exec-1")
    repo.mark_rebuild_job_cancel_requested(job_id)

    repo.mark_rebuild_job_cancelled(job_id, execution_id="exec-1")

    job = repo.get_rebuild_job(job_id)
    assert job is not None
    assert job.status == RebuildJobStatus.CANCELLED
    assert job.completed_at is not None
    # SQLite often loses tzinfo on read; we mainly care that it was set.


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
