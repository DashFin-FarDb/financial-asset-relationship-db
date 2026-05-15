"""Tests for the RecoveryGate component."""

from unittest.mock import MagicMock

import pytest

from src.data.distributed_lock import DistributedLock, LockState
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

    with pytest.raises(ExecutionBlockedError, match="Execution is blocked"):
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

    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus
    
    class DummyJob:
        status = RebuildJobStatus.RUNNING
        job_id = "job-1"

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob())
        assert gate.evaluate_state() == RecoveryAction.UNSAFE
        with pytest.raises(ExecutionBlockedError, match="Execution is blocked"):
            gate.ensure_safe_to_execute()
