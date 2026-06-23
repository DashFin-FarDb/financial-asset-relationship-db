"""Unit tests for the background reconciliation loop."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.app_factory import GraphRuntimeLifecycleState
from src.logic.reconciliation_engine import (
    ActionType,
    ExecutionMode,
    ExecutionSafety,
    Severity,
)
from src.logic.reconciliation_loop import (
    _create_reconciliation_dependencies,
    _run_sync_reconciliation,
    periodic_reconciliation_loop,
)
from src.logic.recovery_gate import ExecutionBlockedError

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_db_engines():
    """Return mock db engines."""
    return MagicMock(), MagicMock()


@pytest.fixture
def mock_session_factory():
    """Return mock session factory."""
    factory = MagicMock()
    factory.return_value.__enter__.return_value = MagicMock()
    return factory


@pytest.fixture
def mock_lock():
    """Return mock lock."""
    lock = MagicMock()
    lock.holder_id = "test-worker"
    return lock


@pytest.fixture
def reconciliation_loop_context(mock_db_engines, mock_session_factory, mock_lock):
    """Return bundled loop dependencies for tests."""
    return SimpleNamespace(
        db_engines=mock_db_engines,
        session_factory=mock_session_factory,
        lock=mock_lock,
    )


def test_create_reconciliation_dependencies(monkeypatch):
    """Verify lock_ttl is bounded before constructing DistributedLock."""
    mock_session_factory_val = MagicMock()
    mock_lock_val = MagicMock()

    create_session_factory_mock = MagicMock(return_value=mock_session_factory_val)
    distributed_lock_mock = MagicMock(return_value=mock_lock_val)

    monkeypatch.setattr("src.data.database.create_session_factory", create_session_factory_mock)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", distributed_lock_mock)

    engine = MagicMock()
    coord_engine = MagicMock()
    lock_ttl = 450

    sf, lock = _create_reconciliation_dependencies(engine, coord_engine, lock_ttl)

    assert sf == mock_session_factory_val
    assert lock == mock_lock_val

    # create_session_factory should be called twice (once for engine, once for coord_engine)
    assert create_session_factory_mock.call_count == 2
    distributed_lock_mock.assert_called_once_with(
        coordination_session_factory=mock_session_factory_val,
        lock_name="graph_rebuild",
        ttl_seconds=300,
    )


def test_run_sync_reconciliation_success(monkeypatch, reconciliation_loop_context, make_reconciliation_plan):
    """Verify single-pass plan consumption under normal execution."""
    plan = make_reconciliation_plan(
        drift_type="none",
        severity=Severity.HIGH,
        actions=(ActionType.NOOP,),
        target_state="healthy",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.CONVERGED,
        reason="Healthy",
    )

    # Mock gate methods
    gate_mock = MagicMock()
    gate_mock.get_reconciliation_plan.return_value = plan
    gate_mock.lock_was_reacquired = False

    # We mock RecoveryGate constructor to return our gate_mock
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", lambda **kwargs: gate_mock)

    # Mock dependencies setup
    monkeypatch.setattr(
        "src.logic.reconciliation_loop._create_reconciliation_dependencies",
        lambda *args, **kwargs: (reconciliation_loop_context.session_factory, reconciliation_loop_context.lock),
    )

    # Also mock metrics to avoid actual prometheus interactions
    mock_duration = MagicMock()
    monkeypatch.setattr("api.metrics.RECONCILIATION_DURATION", mock_duration)

    _run_sync_reconciliation(
        reconciliation_loop_context.db_engines[0], reconciliation_loop_context.db_engines[1], None, 450
    )

    # Gate should query the plan and consume it
    gate_mock.get_reconciliation_plan.assert_called_once()
    gate_mock.consume_reconciliation_plan.assert_called_once_with(plan, cancellation_event=None)

    # Metrics should observe duration
    mock_duration.observe.assert_called_once()

    # Lock release should not be called since lock_was_reacquired is False
    reconciliation_loop_context.lock.release.assert_not_called()


def test_run_sync_reconciliation_releases_reacquired_lock(
    monkeypatch, reconciliation_loop_context, make_reconciliation_plan
):
    """Verify that a reacquired lock is released in the finally block."""
    plan = make_reconciliation_plan(
        drift_type="orphaned_running",
        severity=Severity.HIGH,
        actions=(ActionType.RESET_STATE,),
        target_state="healthy",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason="Orphaned running",
    )

    gate_mock = MagicMock()
    gate_mock.get_reconciliation_plan.return_value = plan
    # Simulate that lock was reacquired during reset execution
    gate_mock.lock_was_reacquired = False
    gate_mock.lock = reconciliation_loop_context.lock

    def _consume_and_mark_reacquired(*args, **kwargs):
        gate_mock.lock_was_reacquired = True

    gate_mock.consume_reconciliation_plan.side_effect = _consume_and_mark_reacquired

    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", lambda **kwargs: gate_mock)
    monkeypatch.setattr(
        "src.logic.reconciliation_loop._create_reconciliation_dependencies",
        lambda *args, **kwargs: (reconciliation_loop_context.session_factory, reconciliation_loop_context.lock),
    )
    monkeypatch.setattr("api.metrics.RECONCILIATION_DURATION", MagicMock())

    _run_sync_reconciliation(
        reconciliation_loop_context.db_engines[0], reconciliation_loop_context.db_engines[1], None, 300
    )

    # Release must be called since lock_was_reacquired is True
    reconciliation_loop_context.lock.release.assert_called_once()


def test_run_sync_reconciliation_lock_release_failure_is_caught(
    monkeypatch, reconciliation_loop_context, make_reconciliation_plan
):
    """Verify that lock release exceptions are handled and do not propagate."""
    plan = make_reconciliation_plan(
        drift_type="orphaned_running",
        severity=Severity.HIGH,
        actions=(ActionType.RESET_STATE,),
        target_state="healthy",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason="Orphaned running",
    )

    gate_mock = MagicMock()
    gate_mock.get_reconciliation_plan.return_value = plan
    gate_mock.lock_was_reacquired = False
    gate_mock.lock = reconciliation_loop_context.lock

    def _consume_and_mark_reacquired(*args, **kwargs):
        gate_mock.lock_was_reacquired = True

    gate_mock.consume_reconciliation_plan.side_effect = _consume_and_mark_reacquired
    # Mock release to fail
    reconciliation_loop_context.lock.release.side_effect = RuntimeError("Release failed")

    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", lambda **kwargs: gate_mock)
    monkeypatch.setattr(
        "src.logic.reconciliation_loop._create_reconciliation_dependencies",
        lambda *args, **kwargs: (reconciliation_loop_context.session_factory, reconciliation_loop_context.lock),
    )
    monkeypatch.setattr("api.metrics.RECONCILIATION_DURATION", MagicMock())

    # We mock log_event to assert that the release failure is logged
    mock_log_event = MagicMock()
    monkeypatch.setattr("src.logic.reconciliation_loop.log_event", mock_log_event)

    # Should not raise RuntimeError
    _run_sync_reconciliation(
        reconciliation_loop_context.db_engines[0], reconciliation_loop_context.db_engines[1], None, 300
    )

    reconciliation_loop_context.lock.release.assert_called_once()

    # Assert it logged the event reconciliation_loop_lock_release_failed
    log_calls = [call[0][2] for call in mock_log_event.call_args_list]
    assert any(ev.event == "reconciliation_loop_lock_release_failed" for ev in log_calls)


def test_run_sync_reconciliation_blocked_error_propagates(
    monkeypatch, reconciliation_loop_context, make_reconciliation_plan
):
    """Verify that ExecutionBlockedError propagates out of the sync loop."""
    plan = make_reconciliation_plan(
        drift_type="lock_lost",
        severity=Severity.CRITICAL,
        actions=(ActionType.ALERT_ONLY,),
        target_state="healthy",
        execution_mode=ExecutionMode.MANUAL,
        safety_state=ExecutionSafety.UNSAFE_SPLIT_BRAIN,
        reason="Lock lost",
    )

    gate_mock = MagicMock()
    gate_mock.get_reconciliation_plan.return_value = plan
    gate_mock.consume_reconciliation_plan.side_effect = ExecutionBlockedError("Blocked", action="alert_only")
    gate_mock.lock_was_reacquired = False

    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", lambda **kwargs: gate_mock)
    monkeypatch.setattr(
        "src.logic.reconciliation_loop._create_reconciliation_dependencies",
        lambda *args, **kwargs: (reconciliation_loop_context.session_factory, reconciliation_loop_context.lock),
    )
    monkeypatch.setattr("api.metrics.RECONCILIATION_DURATION", MagicMock())

    with pytest.raises(ExecutionBlockedError):
        _run_sync_reconciliation(
            reconciliation_loop_context.db_engines[0], reconciliation_loop_context.db_engines[1], None, 300
        )


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_skips_when_not_ready(monkeypatch):
    """Verify loop skips iteration when runtime lifecycle state is not READY."""
    lifecycle_mock = MagicMock(return_value=GraphRuntimeLifecycleState.INITIALIZING)
    monkeypatch.setattr("api.app_factory.get_runtime_lifecycle_state", lifecycle_mock)

    # Mock DB engines setup
    monkeypatch.setattr(
        "src.logic.reconciliation_loop._setup_engines", lambda url, coord_url: (MagicMock(), MagicMock())
    )
    monkeypatch.setattr("src.logic.reconciliation_loop._dispose_engines", lambda e, ce: None)

    # Mock iteration call
    iter_mock = MagicMock()
    monkeypatch.setattr("src.logic.reconciliation_loop._perform_reconciliation_iteration", iter_mock)

    # Stop the loop after 1 iteration
    shutdown_calls = 0

    def mock_is_shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        return shutdown_calls > 1

    await periodic_reconciliation_loop(
        interval_seconds=0.01,
        database_url="sqlite://",
        is_shutdown_fn=mock_is_shutdown,
        run_with_trace_fn=lambda fn, **kwargs: fn(),
    )

    # The iteration should not be called
    iter_mock.assert_not_called()


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_runs_iteration_when_ready(monkeypatch):
    """Verify loop executes iteration when runtime lifecycle state is READY."""
    lifecycle_mock = MagicMock(return_value=GraphRuntimeLifecycleState.READY)
    monkeypatch.setattr("api.app_factory.get_runtime_lifecycle_state", lifecycle_mock)

    monkeypatch.setattr(
        "src.logic.reconciliation_loop._setup_engines", lambda url, coord_url: (MagicMock(), MagicMock())
    )
    monkeypatch.setattr("src.logic.reconciliation_loop._dispose_engines", lambda e, ce: None)

    from unittest.mock import AsyncMock

    # Mock iteration call (async)
    iter_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("src.logic.reconciliation_loop._perform_reconciliation_iteration", iter_mock)

    # Stop the loop after 1 iteration
    shutdown_calls = 0

    def mock_is_shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        return shutdown_calls > 1

    await periodic_reconciliation_loop(
        interval_seconds=0.001,
        database_url="sqlite://",
        is_shutdown_fn=mock_is_shutdown,
        run_with_trace_fn=lambda fn, **kwargs: fn(),
    )

    # The iteration should be called
    iter_mock.assert_called_once()


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_backoff_on_error(monkeypatch):
    """Verify loop backs off on error and resets on success."""
    lifecycle_mock = MagicMock(return_value=GraphRuntimeLifecycleState.READY)
    monkeypatch.setattr("api.app_factory.get_runtime_lifecycle_state", lifecycle_mock)

    monkeypatch.setattr(
        "src.logic.reconciliation_loop._setup_engines", lambda url, coord_url: (MagicMock(), MagicMock())
    )
    monkeypatch.setattr("src.logic.reconciliation_loop._dispose_engines", lambda e, ce: None)

    # First iteration fails with exception, second succeeds
    iter_calls = 0

    async def mock_perform_reconciliation_iteration(*args, **kwargs):
        nonlocal iter_calls
        iter_calls += 1
        if iter_calls == 1:
            raise RuntimeError("Database error")
        return None

    monkeypatch.setattr(
        "src.logic.reconciliation_loop._perform_reconciliation_iteration", mock_perform_reconciliation_iteration
    )

    # Let the loop execute twice, then shutdown
    shutdown_calls = 0

    def mock_is_shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        return shutdown_calls > 2

    # Capture sleep duration to verify backoff is applied
    sleep_durations = []

    async def mock_sleep(seconds):
        sleep_durations.append(seconds)

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    await periodic_reconciliation_loop(
        interval_seconds=2.0,
        database_url="sqlite://",
        is_shutdown_fn=mock_is_shutdown,
        run_with_trace_fn=lambda fn, **kwargs: fn(),
    )

    # Assert loop ran twice
    assert iter_calls == 2

    # The sleep durations should be exactly 3:
    # 1. 2.0 (initial)
    # 2. 4.xxxx (backed off after first iter failed)
    # 3. 2.0 (reset after second iter succeeded)
    assert len(sleep_durations) == 3
    assert sleep_durations[0] == 2.0
    assert sleep_durations[1] > 2.0
    assert sleep_durations[2] == 2.0


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_does_not_backoff_on_blocked_state(monkeypatch):
    """Verify expected recovery gate blocks do not trigger transient-error backoff."""
    lifecycle_mock = MagicMock(return_value=GraphRuntimeLifecycleState.READY)
    monkeypatch.setattr("api.app_factory.get_runtime_lifecycle_state", lifecycle_mock)

    monkeypatch.setattr(
        "src.logic.reconciliation_loop._setup_engines", lambda url, coord_url: (MagicMock(), MagicMock())
    )
    monkeypatch.setattr("src.logic.reconciliation_loop._dispose_engines", lambda e, ce: None)

    iter_calls = 0

    async def mock_perform_reconciliation_iteration(*args, **kwargs):
        nonlocal iter_calls
        iter_calls += 1
        if iter_calls == 1:
            raise ExecutionBlockedError("blocked", action="wait", inconsistency_type="wait_for_convergence")
        return None

    monkeypatch.setattr(
        "src.logic.reconciliation_loop._perform_reconciliation_iteration", mock_perform_reconciliation_iteration
    )

    shutdown_calls = 0

    def mock_is_shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        return shutdown_calls > 2

    sleep_durations = []

    async def mock_sleep(seconds):
        sleep_durations.append(seconds)

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    await periodic_reconciliation_loop(
        interval_seconds=2.0,
        database_url="sqlite://",
        is_shutdown_fn=mock_is_shutdown,
        run_with_trace_fn=lambda fn, **kwargs: fn(),
    )

    assert iter_calls == 2
    assert sleep_durations == [2.0, 2.0, 2.0]
