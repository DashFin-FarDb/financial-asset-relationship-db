"""Tests for startup reconciliation via RecoveryGate."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.distributed_lock import DistributedLock, LockState
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate


@pytest.fixture
def mock_session_factory():
    """Return a mock session factory."""
    factory = MagicMock()
    session = MagicMock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    factory.return_value = session
    return factory


@pytest.fixture
def mock_lock():
    """Return a mock DistributedLock."""
    lock = MagicMock(spec=DistributedLock)
    lock.check_state.return_value = LockState.VALID
    lock.holder_id = "startup-worker-1"
    lock.acquire.return_value = True
    return lock


def test_startup_reconciliation_passes_with_consistent_state(mock_session_factory, mock_lock):
    """Test that startup reconciliation passes when state is consistent."""
    # Setup: No active job in DB
    mock_repo = MagicMock()
    mock_repo.get_active_rebuild_state.return_value = None

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should not raise - consistent state
        gate.ensure_safe_to_execute()


def test_gate_waits_on_unknown_lock_with_no_active_job(mock_session_factory, mock_lock):
    """Test that the gate returns WAIT for UNKNOWN lock + no active job (clean install).

    The gate itself raises ExecutionBlockedError(action="wait", inconsistency_type="none") for
    this case.  The startup reconciliation catches this specific action+inconsistency combination
    and allows startup to proceed (see _run_startup_reconciliation in app_factory.py).
    Other WAIT cases (e.g. CRASH_SUSPICION+valid-lock) still block startup.
    """
    # Setup: clean install / startup path with no active job in DB
    mock_repo = MagicMock()
    mock_repo.get_active_rebuild_state.return_value = None
    mock_lock.check_state.return_value = LockState.UNKNOWN

    from src.logic.rebuild_recovery import RecoveryAction

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # The gate returns WAIT — no inconsistency, but lock not yet acquired.
        assert gate.evaluate_state() == RecoveryAction.WAIT

        # ensure_safe_to_execute raises with action="wait" AND inconsistency_type="none";
        # startup only bypasses the block when both match (clean-install semantics).
        with pytest.raises(ExecutionBlockedError) as exc_info:
            gate.ensure_safe_to_execute()
        assert exc_info.value.action == "wait"
        assert exc_info.value.inconsistency_type == "none"


def test_startup_reconciliation_performs_reset_for_orphaned_job(mock_session_factory, mock_lock):
    """Test that startup reconciliation performs RESET recovery for orphaned job."""
    from datetime import datetime, timezone

    # Setup: Orphaned RUNNING job in DB
    orphaned_job = RebuildJobORM(
        job_id="orphaned-job-1",
        requested_by="previous-worker",
        status=RebuildJobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        active_worker_id="dead-worker",
        last_heartbeat_at=datetime(2020, 1, 1, tzinfo=timezone.utc),  # Very stale
    )

    mock_repo = MagicMock()
    # Calls: 1) initial eval, 2) inside _perform_reset_recovery, 3) re-eval after RESET
    mock_repo.get_active_rebuild_state.side_effect = [orphaned_job, orphaned_job, None]
    mock_repo.mark_rebuild_job_failed = MagicMock()

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should perform RESET recovery and allow execution
        gate.ensure_safe_to_execute()

        # Verify RESET was performed
        mock_repo.mark_rebuild_job_failed.assert_called_once()
        call_args = mock_repo.mark_rebuild_job_failed.call_args
        assert call_args[0][0] == "orphaned-job-1"
        assert call_args[1]["failure_category"] == "recovery_reset"


def test_startup_reconciliation_blocks_on_lost_lock_state(mock_session_factory, mock_lock):
    """Test that startup reconciliation blocks when lock state is LOST."""
    mock_lock.check_state.return_value = LockState.LOST

    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
        lock_ttl_seconds=300,
    )

    with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
        gate.ensure_safe_to_execute()


def test_startup_reconciliation_blocks_on_unknown_lock_state(mock_session_factory, mock_lock):
    """Test that startup reconciliation blocks when lock state is UNKNOWN and a job is active."""
    mock_lock.check_state.return_value = LockState.UNKNOWN

    mock_repo = MagicMock()
    active_job = MagicMock(spec=RebuildJobORM)
    active_job.status = RebuildJobStatus.RUNNING
    mock_repo.get_active_rebuild_state.return_value = active_job

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        with pytest.raises(ExecutionBlockedError) as exc_info:
            gate.ensure_safe_to_execute()
        assert exc_info.value.action in ("alert_only", "wait")
        assert exc_info.value.inconsistency_type != "none"


def test_startup_reconciliation_blocks_on_db_error(mock_session_factory, mock_lock):
    """Test that startup reconciliation blocks when DB query fails."""
    from sqlalchemy.exc import OperationalError

    mock_repo = MagicMock()
    mock_repo.get_active_rebuild_state.side_effect = OperationalError(
        "DB connection failed", params=None, orig=Exception("Connection error")
    )

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
            gate.ensure_safe_to_execute()


def test_startup_reconciliation_blocks_on_fresh_remote_heartbeat(mock_session_factory, mock_lock):
    """Test that startup reconciliation blocks when remote worker has fresh heartbeat."""
    from datetime import datetime, timezone

    # Setup: RUNNING job with different worker but FRESH heartbeat
    remote_job = RebuildJobORM(
        job_id="remote-job-1",
        requested_by="remote-worker",
        status=RebuildJobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        active_worker_id="remote-worker-id",  # Different from lock holder
        last_heartbeat_at=datetime.now(timezone.utc),  # Fresh heartbeat
    )

    mock_repo = MagicMock()
    mock_repo.get_active_rebuild_state.return_value = remote_job

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should block - remote worker is healthy
        with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
            gate.ensure_safe_to_execute()


def test_startup_reconciliation_reacquires_lock_before_reset(mock_session_factory, mock_lock):
    """Test that startup reconciliation reacquires lock if expired before RESET."""
    from datetime import datetime, timezone

    # Setup: Orphaned job + expired lock
    orphaned_job = RebuildJobORM(
        job_id="orphaned-job-2",
        requested_by="previous-worker",
        status=RebuildJobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        active_worker_id="dead-worker",
        last_heartbeat_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )

    # First check: EXPIRED (initial eval), second check (during RESET): EXPIRED,
    # third check (re-eval after RESET): VALID
    mock_lock.check_state.side_effect = [LockState.EXPIRED, LockState.EXPIRED, LockState.VALID]
    mock_lock.acquire.return_value = True

    mock_repo = MagicMock()
    # Calls: 1) initial eval, 2) inside _perform_reset_recovery, 3) re-eval after RESET
    mock_repo.get_active_rebuild_state.side_effect = [orphaned_job, orphaned_job, None]
    mock_repo.mark_rebuild_job_failed = MagicMock()

    with patch("src.logic.recovery_gate.AssetGraphRepository", return_value=mock_repo):
        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should reacquire lock and perform RESET
        gate.ensure_safe_to_execute()

        # Verify lock was reacquired
        mock_lock.acquire.assert_called_once()
        assert gate.lock_was_reacquired is True
        # Verify RESET was performed
        mock_repo.mark_rebuild_job_failed.assert_called_once()
