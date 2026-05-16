"""Tests for the RecoveryGate component."""

from unittest.mock import MagicMock

import pytest

from src.data.distributed_lock import DistributedLock, LockState
from src.logic.rebuild_failure_detection import InconsistencyType
from src.logic.rebuild_recovery import RecoveryAction
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate


@pytest.fixture
def mock_session_factory():
    """Return a mock session factory."""
    factory = MagicMock()
    factory.return_value.__enter__.return_value = MagicMock()
    return factory


@pytest.fixture
def mock_lock():
    """Return a mock DistributedLock."""
    lock = MagicMock(spec=DistributedLock)
    lock.check_state.return_value = LockState.VALID
    lock.holder_id = "worker-1"
    return lock


def test_recovery_gate_blocks_on_unknown_lock(mock_session_factory, mock_lock):
    """Test that RecoveryGate blocks execution when lock state is UNKNOWN."""
    mock_lock.check_state.return_value = LockState.UNKNOWN
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    assert gate.evaluate_state() == RecoveryAction.UNSAFE

    with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
        gate.ensure_safe_to_execute()


def test_recovery_gate_blocks_on_lost_lock(mock_session_factory, mock_lock):
    """Test that RecoveryGate blocks execution when lock state is LOST."""
    mock_lock.check_state.return_value = LockState.LOST
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    assert gate.evaluate_state() == RecoveryAction.UNSAFE


def test_recovery_gate_resume_on_clean_state(mock_session_factory, mock_lock):
    """Test that RecoveryGate allows execution on clean state."""
    mock_lock.check_state.return_value = LockState.VALID

    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: None)
        assert gate.evaluate_state() == RecoveryAction.RESUME
        gate.ensure_safe_to_execute()  # Should not raise


def test_recovery_gate_blocks_on_orphan_with_valid_lock(mock_session_factory, mock_lock):
    """Test that RecoveryGate blocks if there's an orphan running job but we hold the lock."""
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "worker-1"

    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "worker-1"

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob())
        assert gate.evaluate_state() == RecoveryAction.UNSAFE
        with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
            gate.ensure_safe_to_execute()


def test_recovery_gate_increments_recovery_metric_on_detected_inconsistency(
    mock_session_factory, mock_lock, monkeypatch
):
    """Detected inconsistencies should increment recovery trigger metrics."""
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "worker-1"
    metric_calls: list[str] = []
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        increment_recovery_trigger=metric_calls.append,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "worker-1"

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob()
    )
    assert gate.evaluate_state() == RecoveryAction.UNSAFE
    assert metric_calls == [InconsistencyType.ORPHANED_RUNNING.value]


def test_recovery_gate_blocks_when_multiple_running_jobs_detected(mock_session_factory, mock_lock, monkeypatch):
    """Multiple running DB jobs should block execution as unsafe."""
    mock_lock.check_state.return_value = LockState.VALID
    metric_calls: list[str] = []
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        increment_recovery_trigger=metric_calls.append,
        runtime_has_active_executor=False,
    )

    def _raise_multiple_running(_self):
        raise ValueError("Multiple rebuild jobs are in RUNNING state")

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state",
        _raise_multiple_running,
    )
    assert gate.evaluate_state() == RecoveryAction.UNSAFE
    assert metric_calls == [InconsistencyType.ORPHANED_RUNNING.value]


def test_recovery_gate_error_message_includes_decision_reason(mock_session_factory, mock_lock, monkeypatch):
    """Blocked executions should include actionable reason details."""
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "worker-1"
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "other-worker"

    # Mock the repository to return orphaned job for initial check
    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob()
    )
    
    # Mock session.get() to fail the mark_rebuild_job_failed call
    # This simulates reset recovery failure
    mock_session = mock_session_factory.return_value
    mock_session.get.return_value = None  # Job not found - causes ValueError
    
    with pytest.raises(ExecutionBlockedError, match=r"Reset recovery failed"):
        gate.ensure_safe_to_execute()


def test_recovery_gate_orphaned_with_new_lock_owner_returns_reset(mock_session_factory, mock_lock, monkeypatch):
    """Orphaned jobs owned by another worker should remain recoverable via RESET."""
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "new-worker"
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "stale-worker"

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob()
    )
    assert gate.evaluate_state() == RecoveryAction.RESET
