"""Tests for the RecoveryGate component."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.data.distributed_lock import DistributedLock, LockState
from src.logic.rebuild_failure_detection import InconsistencyType
from src.logic.rebuild_recovery import RecoveryAction
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

UTC = timezone.utc


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


def _make_reset_required_plan(
    make_reconciliation_plan,
    *,
    drift_type="orphaned_running",
    execution_mode=None,
    reason=None,
):
    """Return a reset-required reconciliation plan for recovery-gate boundary tests."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, Severity

    if execution_mode is None:
        execution_mode = ExecutionMode.AUTOMATIC
    if reason is None:
        reason = f"Reset required for {drift_type}"
    return make_reconciliation_plan(
        drift_type=drift_type,
        severity=Severity.HIGH,
        actions=(ActionType.RESET_STATE,),
        target_state="healthy",
        execution_mode=execution_mode,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason=reason,
    )


def _make_plan(make_reconciliation_plan, overrides):
    """Return a reconciliation plan with the common healthy target state."""
    defaults = {"target_state": "healthy"}
    return make_reconciliation_plan(**{**defaults, **overrides})


def test_recovery_gate_waits_on_unknown_lock_with_no_active_job(mock_session_factory, mock_lock):
    """Test that RecoveryGate returns WAIT (allowing startup) when lock is UNKNOWN and no active job exists.

    UNKNOWN lock + no active job indicates a clean install or naturally-expired lock.
    The gate returns WAIT to allow the executor to acquire the lock before the first
    rebuild, rather than blocking startup.
    """
    from unittest.mock import patch

    mock_lock.check_state.return_value = LockState.UNKNOWN

    # Mock repository to return no active job (clean install scenario)
    with patch("src.logic.recovery_gate.AssetGraphRepository") as mock_repo_class:
        mock_repo = mock_repo_class.return_value
        mock_repo.get_active_rebuild_state.return_value = None

        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
        )

        # UNKNOWN with no job should return WAIT (needs to acquire lock but safe to proceed)
        assert gate.evaluate_state() == RecoveryAction.WAIT

        # ensure_safe_to_execute blocks with WAIT action; startup handles this via exc.action
        with pytest.raises(ExecutionBlockedError, match="action=wait") as exc_info:
            gate.ensure_safe_to_execute()
        # Verify both attributes so startup can safely allow clean-install WAIT
        assert exc_info.value.action == "wait"
        assert exc_info.value.inconsistency_type == "none"


def test_execution_blocked_error_exposes_action_for_unsafe(mock_session_factory, mock_lock):
    """ExecutionBlockedError.action is set for UNSAFE decisions so callers can branch without re-evaluating."""
    mock_lock.check_state.return_value = LockState.LOST
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    # LOST → UNSAFE; verify action and inconsistency_type attributes.
    with pytest.raises(ExecutionBlockedError) as exc_info:
        gate.ensure_safe_to_execute()
    assert exc_info.value.action == "alert_only"
    # The new engine properly models lock_lost as a drift_type, so we expect "lock_lost"
    # rather than None.
    assert exc_info.value.inconsistency_type == "lock_lost"


def test_recovery_gate_blocks_on_lost_lock(mock_session_factory, mock_lock):
    """Test that RecoveryGate blocks execution when lock state is LOST."""
    mock_lock.check_state.return_value = LockState.LOST
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    # Verify both decision API and execution blocking
    assert gate.evaluate_state() == "alert_only"

    with pytest.raises(ExecutionBlockedError, match="Execution blocked"):
        gate.ensure_safe_to_execute()


def test_recovery_gate_lost_state_does_not_attempt_reset(mock_session_factory, mock_lock):
    """Test that RecoveryGate does not attempt RESET recovery when lock state is LOST.

    LOST state indicates DB connectivity failure, so we cannot safely mutate state.
    This test verifies LOST-specific behavior: immediate blocking without state queries.
    """
    mock_lock.check_state.return_value = LockState.LOST
    mock_lock.acquire = MagicMock()  # Should never be called

    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    # LOST state should block with action=alert_only
    with pytest.raises(ExecutionBlockedError, match="action=alert_only"):
        gate.ensure_safe_to_execute()

    mock_session_factory.assert_not_called()
    # LOST-specific verification: no lock reacquisition attempted (no RESET recovery)
    mock_lock.acquire.assert_not_called()


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
        """Mock rebuild job."""

        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "worker-1"

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob())
        assert gate.evaluate_state() == "alert_only"
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
        """Mock rebuild job."""

        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "worker-1"

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob()
    )
    assert gate.evaluate_state() == "alert_only"
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
        """Raise an exception to mock detecting multiple running jobs."""
        raise ValueError("Multiple rebuild jobs are in RUNNING state")

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state",
        _raise_multiple_running,
    )
    assert gate.evaluate_state() == "alert_only"
    # Error paths do not increment recovery triggers per _create_unsafe_decision_from_error
    # See recovery_gate.py lines 78-86: early return before metric increment
    assert metric_calls == []


def test_recovery_gate_error_message_includes_decision_reason(mock_session_factory, mock_lock, monkeypatch):
    """Blocked executions should include actionable reason details."""
    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "worker-1"
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
        enable_automatic_recovery=True,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        """Mock rebuild job."""

        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "other-worker"
        last_heartbeat_at = None  # Missing heartbeat = stale/orphaned

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
        """Mock rebuild job."""

        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "stale-worker"
        last_heartbeat_at = None  # Missing heartbeat = stale/orphaned

    monkeypatch.setattr(
        "src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: DummyJob()
    )
    assert gate.evaluate_state() == RecoveryAction.RESET


def test_consume_converged_plan_allows_execution(mock_session_factory, mock_lock, make_reconciliation_plan):
    """Converged plan should allow execution without raising errors."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, Severity

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock)
    plan = _make_plan(
        make_reconciliation_plan,
        {
            "drift_type": "none",
            "severity": Severity.NONE,
            "actions": (ActionType.NOOP,),
            "execution_mode": ExecutionMode.AUTOMATIC,
            "safety_state": ExecutionSafety.CONVERGED,
            "reason": "Graph is healthy",
        },
    )
    # Should not raise any exception
    gate.consume_reconciliation_plan(plan)


def test_consume_blocking_plans_fail_closed(mock_session_factory, mock_lock, make_reconciliation_plan):
    """Blocking plans must raise with the expected action and avoid reset mutation."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, Severity

    cases = [
        (
            "unknown_noop",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock),
            _make_plan(
                make_reconciliation_plan,
                {
                    "drift_type": "manual_investigation",
                    "severity": Severity.HIGH,
                    "actions": (ActionType.NOOP,),
                    "execution_mode": ExecutionMode.MANUAL,
                    "safety_state": ExecutionSafety.MANUAL_INVESTIGATION,
                    "reason": "Malformed plan should fail closed",
                },
            ),
            "unsafe",
            "manual_investigation",
        ),
        (
            "wait_required",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock),
            _make_plan(
                make_reconciliation_plan,
                {
                    "drift_type": "wait_for_convergence",
                    "severity": Severity.MEDIUM,
                    "actions": (ActionType.WAIT_FOR_CONVERGENCE,),
                    "execution_mode": ExecutionMode.AUTOMATIC,
                    "safety_state": ExecutionSafety.WAIT_REQUIRED,
                    "reason": "Waiting for active build",
                },
            ),
            "wait",
            "wait_for_convergence",
        ),
        (
            "alert_only",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock),
            _make_plan(
                make_reconciliation_plan,
                {
                    "drift_type": "stale_ownership",
                    "severity": Severity.HIGH,
                    "actions": (ActionType.ALERT_ONLY,),
                    "execution_mode": ExecutionMode.MANUAL,
                    "safety_state": ExecutionSafety.MANUAL_INVESTIGATION,
                    "reason": "Stale ownership detected",
                },
            ),
            "alert_only",
            "stale_ownership",
        ),
        (
            "evaluation_failed",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock),
            _make_plan(
                make_reconciliation_plan,
                {
                    "drift_type": "evaluation_failed",
                    "severity": Severity.CRITICAL,
                    "actions": (ActionType.ALERT_ONLY,),
                    "execution_mode": ExecutionMode.MANUAL,
                    "safety_state": ExecutionSafety.EVALUATION_FAILED,
                    "reason": "State query failed",
                },
            ),
            "alert_only",
            "evaluation_failed",
        ),
        (
            "deferred_reset",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock),
            _make_reset_required_plan(
                make_reconciliation_plan,
                execution_mode=ExecutionMode.DEFERRED,
                reason="Orphaned job reset deferred",
            ),
            "wait",
            "orphaned_running",
        ),
        (
            "automatic_reset_disabled",
            RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=False),
            _make_reset_required_plan(make_reconciliation_plan, reason="Auto-reset orphaned job"),
            "alert_only",
            "orphaned_running",
        ),
    ]

    for name, gate, plan, expected_action, expected_inconsistency in cases:
        gate._execute_reset_path = MagicMock()
        with pytest.raises(ExecutionBlockedError) as exc_info:
            gate.consume_reconciliation_plan(plan)

        assert exc_info.value.action == expected_action, name
        assert exc_info.value.inconsistency_type == expected_inconsistency, name
        gate._execute_reset_path.assert_not_called()


def test_recovery_gate_caps_lock_ttl_seconds(mock_session_factory, mock_lock):
    """The recovery gate should cap lock TTL at the distributed-lock maximum."""
    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, lock_ttl_seconds=450)

    assert gate.lock_ttl_seconds == 300


def test_consume_automatic_reset_plan_calls_reset_path(mock_session_factory, mock_lock, make_reconciliation_plan):
    """Automatic reset plans must trigger the reset execution pathway."""
    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(make_reconciliation_plan, reason="Auto-reset orphaned job")

    # Mock _execute_reset_path so we don't hit the DB/lock layer in this test
    gate._execute_reset_path = MagicMock()

    gate.consume_reconciliation_plan(plan)
    gate._execute_reset_path.assert_called_once_with(plan, None)


def test_consume_immediate_reset_plan_calls_reset_path_when_automatic_recovery_disabled(
    mock_session_factory, mock_lock, make_reconciliation_plan
):
    """Immediate reset plans remain explicitly authorized even when automatic recovery is disabled."""
    from src.logic.reconciliation_engine import ExecutionMode

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=False)
    plan = _make_reset_required_plan(
        make_reconciliation_plan,
        execution_mode=ExecutionMode.IMMEDIATE,
        reason="Immediate reset orphaned job",
    )
    gate._execute_reset_path = MagicMock()

    gate.consume_reconciliation_plan(plan)

    gate._execute_reset_path.assert_called_once_with(plan, None)


def test_consume_reset_plan_rechecks_state_after_reset(
    mock_session_factory, mock_lock, monkeypatch, make_reconciliation_plan
):
    """Reset path must recheck plan post-reset and block if still unsafe."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, Severity

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(make_reconciliation_plan, reason="Auto-reset orphaned job")

    # Mock get_active_rebuild_state to do nothing and succeed
    monkeypatch.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: None)

    # Mock get_reconciliation_plan to return a non-resume plan after reset
    unsafe_plan = make_reconciliation_plan(
        drift_type="lock_lost",
        severity=Severity.CRITICAL,
        actions=(ActionType.ALERT_ONLY,),
        target_state="healthy",
        execution_mode=ExecutionMode.MANUAL,
        safety_state=ExecutionSafety.UNSAFE_SPLIT_BRAIN,
        reason="Lock lost post-reset",
    )

    def mock_get_reconciliation_plan(increment_metric=True):
        """Return an unsafe mock reconciliation plan."""
        return unsafe_plan

    gate.get_reconciliation_plan = mock_get_reconciliation_plan

    with pytest.raises(ExecutionBlockedError, match="Reset recovery completed but state still unsafe"):
        gate.consume_reconciliation_plan(plan)


def test_consume_reset_respects_cancellation_before_mutation(mock_session_factory, mock_lock, make_reconciliation_plan):
    """Cancellation event set before or during reset should abort execution without mutation."""
    import threading

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(make_reconciliation_plan, reason="Auto-reset orphaned job")

    cancel_event = threading.Event()
    cancel_event.set()

    mock_perform_reset = MagicMock()
    gate._perform_reset_recovery = mock_perform_reset

    from src.logic.reconciliation_engine import RebuildCancelledError

    # Execute plan with cancelled event
    with pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"):
        gate.consume_reconciliation_plan(plan, cancellation_event=cancel_event)

    mock_perform_reset.assert_not_called()


def test_reset_lock_reacquisition_timeout_uses_plan_drift_type(
    mock_session_factory, mock_lock, monkeypatch, make_reconciliation_plan
):
    """Lock reacquisition timeout should preserve the plan drift type in the block error."""
    from src.data.distributed_lock import LockAcquisitionTimeout

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(
        make_reconciliation_plan,
        drift_type="crash_suspicion",
        reason="Crash suspected",
    )
    mock_lock.check_state.return_value = LockState.EXPIRED
    mock_lock.acquire.side_effect = LockAcquisitionTimeout("timeout")
    monkeypatch.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: None)

    with pytest.raises(ExecutionBlockedError) as exc_info:
        gate.consume_reconciliation_plan(plan)

    assert exc_info.value.action == "wait"
    assert exc_info.value.inconsistency_type == "crash_suspicion"


def test_reset_lock_reacquisition_requires_valid_lock_after_acquire(
    mock_session_factory, mock_lock, monkeypatch, make_reconciliation_plan
):
    """Reset recovery must block if reacquisition does not produce a valid lock state."""
    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(
        make_reconciliation_plan,
        drift_type="crash_suspicion",
        reason="Crash suspected",
    )
    mock_lock.check_state.side_effect = [LockState.EXPIRED, LockState.EXPIRED]
    mock_lock.acquire.return_value = True
    monkeypatch.setattr("src.logic.recovery_gate.AssetGraphRepository.get_active_rebuild_state", lambda self: None)

    with pytest.raises(ExecutionBlockedError) as exc_info:
        gate.consume_reconciliation_plan(plan)

    assert exc_info.value.action == "wait"
    assert exc_info.value.inconsistency_type == "crash_suspicion"
    mock_lock.acquire.assert_called_once_with(max_retries=30, timeout_seconds=30.0)
    assert gate.lock_was_reacquired is False


def test_reset_blocks_fresh_remote_owner_as_stale_ownership(
    mock_session_factory, mock_lock, monkeypatch, make_reconciliation_plan
):
    """A fresh heartbeat from a different worker should block as stale ownership, not orphaned running."""
    from src.data.db_models import RebuildJobStatus

    gate = RecoveryGate(session_factory=mock_session_factory, lock=mock_lock, enable_automatic_recovery=True)
    plan = _make_reset_required_plan(
        make_reconciliation_plan,
        drift_type="stale_ownership",
        reason="Ownership mismatch with fresh heartbeat",
    )

    fresh_remote_job = SimpleNamespace(
        status=RebuildJobStatus.RUNNING,
        job_id="job-1",
        execution_id="exec-1",
        active_worker_id="remote-worker",
        last_heartbeat_at=datetime.now(UTC),
    )

    mock_lock.holder_id = "current-worker"
    repo = MagicMock()
    repo.get_active_rebuild_state.return_value = fresh_remote_job
    monkeypatch.setattr("src.logic.recovery_gate.AssetGraphRepository", lambda _session: repo)

    with pytest.raises(ExecutionBlockedError) as exc_info:
        gate.consume_reconciliation_plan(plan)

    assert exc_info.value.action == "unsafe"
    assert exc_info.value.inconsistency_type == "stale_ownership"
    repo.mark_rebuild_job_failed.assert_not_called()


def test_reset_active_job_blocks_on_lock_loss_and_guards_rollback(mock_session_factory, mock_lock, monkeypatch):
    """Test _reset_active_job guards against rollback failure and missing lock holder."""
    gate = RecoveryGate(
        session_factory=mock_session_factory,
        lock=mock_lock,
        runtime_has_active_executor=False,
    )

    from src.data.db_models import RebuildJobStatus

    class DummyJob:
        """Mock rebuild job."""

        status = RebuildJobStatus.RUNNING
        job_id = "job-1"
        active_worker_id = "stale-worker"
        execution_id = "exec-1"
        last_heartbeat_at = None

    mock_lock.check_state.return_value = LockState.VALID
    mock_lock.holder_id = "worker-1"

    mock_session = mock_session_factory.return_value
    mock_session.rollback.side_effect = RuntimeError("DB connection lost during rollback")

    repo = MagicMock()

    def _lose_lock(*args, **kwargs):
        """Mock side effect to simulate losing the lock."""
        mock_lock.holder_id = None

    repo.mark_rebuild_job_failed.side_effect = _lose_lock

    with pytest.raises(ExecutionBlockedError, match="lock lost"):
        gate._reset_active_job(DummyJob(), repo, mock_session, "test_drift")

    assert mock_session.rollback.call_count == 1
