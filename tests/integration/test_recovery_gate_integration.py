"""Integration tests for RecoveryGate with a real SQLite database.

These tests exercise the full stack: ORM models, repository, distributed lock,
and recovery gate — all backed by an in-memory SQLite engine.  They prove that
the recovery gate correctly detects inconsistent state and performs RESET recovery
without relying on mocks for the persistence layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.data.database import create_session_factory, init_db
from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

_LOCK_NAME = "graph_rebuild"
_LOCK_TTL = 300


@pytest.fixture()
def sqlite_engine():
    """Return an in-memory SQLite engine with the full schema applied."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(sqlite_engine):
    """Return a session factory bound to the in-memory SQLite engine."""
    return create_session_factory(sqlite_engine)


def test_recovery_gate_passes_with_clean_db(session_factory):
    """RecoveryGate allows execution when there are no running rebuild jobs.

    The lock is pre-acquired so that the gate sees a VALID lock state and returns
    RESUME (clean state, no inconsistency detected).
    """
    lock = DistributedLock(
        session_factory=session_factory,
        lock_name=_LOCK_NAME,
        ttl_seconds=_LOCK_TTL,
    )
    # Pre-acquire the lock so check_state() returns VALID → gate returns RESUME.
    assert lock.acquire(), "Expected to acquire lock on clean DB"

    try:
        gate = RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=_LOCK_TTL,
        )

        # No running jobs and a valid lock: gate should allow execution without error.
        gate.ensure_safe_to_execute()
    finally:
        lock.release()

    # Lock should have been released.
    assert lock.check_state() != LockState.VALID


def test_recovery_gate_resets_orphaned_running_job(session_factory):
    """RecoveryGate performs RESET recovery for an orphaned RUNNING job.

    Scenario: A RUNNING job exists in the DB with an EXPIRED distributed lock
    (simulating a crashed worker whose lock TTL passed).  The gate detects
    ORPHANED_RUNNING, reacquires the lock, marks the job FAILED, then allows
    execution to continue.
    """
    from sqlalchemy import insert

    from src.data.db_models import DistributedLockORM, RebuildJobStatus

    # Create a RUNNING job.
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="test-worker")
        repo.mark_rebuild_job_running(job_id)
        session.commit()

    # Insert an EXPIRED lock row to simulate the previous worker's lock.
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=400)
    with session_scope(session_factory) as session:
        session.execute(
            insert(DistributedLockORM).values(
                lock_name=_LOCK_NAME,
                holder_id="previous-worker-id",
                expires_at=past,
                created_at=past,
                updated_at=past,
            )
        )
        session.commit()

    lock = DistributedLock(
        session_factory=session_factory,
        lock_name=_LOCK_NAME,
        ttl_seconds=_LOCK_TTL,
    )
    gate = RecoveryGate(
        session_factory=session_factory,
        lock=lock,
        runtime_has_active_executor=False,
        lock_ttl_seconds=_LOCK_TTL,
    )

    # Gate should detect ORPHANED_RUNNING → perform RESET → allow execution.
    gate.ensure_safe_to_execute()

    # Verify the orphaned job was transitioned to FAILED.
    with session_scope(session_factory) as session:
        from src.data.db_models import RebuildJobORM

        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        assert job.status == RebuildJobStatus.FAILED
        assert job.sanitized_failure_category == "recovery_reset"


def test_recovery_gate_blocks_on_lost_lock_state(session_factory):
    """RecoveryGate raises ExecutionBlockedError when the lock state is LOST.

    A LOST state indicates DB connectivity failure.  The gate must block
    execution without attempting any state mutation.
    """
    from unittest.mock import MagicMock

    lock = MagicMock(spec=DistributedLock)
    lock.check_state.return_value = LockState.LOST
    lock.holder_id = "startup-test-worker"

    gate = RecoveryGate(
        session_factory=session_factory,
        lock=lock,
        runtime_has_active_executor=False,
        lock_ttl_seconds=_LOCK_TTL,
    )

    with pytest.raises(ExecutionBlockedError):
        gate.ensure_safe_to_execute()

    # LOST state must not trigger any lock acquisition attempt.
    lock.acquire.assert_not_called()
