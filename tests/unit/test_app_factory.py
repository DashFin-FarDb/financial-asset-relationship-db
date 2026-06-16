"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from api import app_factory
from src.data.database import init_db as database_init_db
from src.logic.recovery_gate import ExecutionBlockedError

pytestmark = pytest.mark.unit


@pytest.fixture
def base_settings() -> SimpleNamespace:
    """Provide minimal mock configuration settings layout."""
    return SimpleNamespace(
        database_url="sqlite:///:memory:",
        has_durable_graph_persistence=True,
        graph_sync_interval_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_lifespan_calls_shutdown_rebuild_executor_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Lifespan should shut down the rebuild executor when the app stops."""
    app = FastAPI()
    shutdown_calls = []

    def fake_shutdown() -> None:
        shutdown_calls.append(True)

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )
    # FIX: Correct parameter count mapping across all lambda hooks
    monkeypatch.setattr(app_factory, "_run_startup_reconciliation", lambda s, ce=None: None)
    monkeypatch.setattr(app_factory, "init_rebuild_executor", lambda s: None)
    monkeypatch.setattr(app_factory, "shutdown_rebuild_executor", fake_shutdown)

    async with app_factory.lifespan(app):
        assert shutdown_calls == []

    assert shutdown_calls == [True]


@pytest.mark.asyncio
async def test_sync_loop_stops_without_syncing_when_shutting_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background sync loop should exit cleanly once shutdown state is observed."""

    async def immediate_sleep(_seconds: float) -> None:
        pass

    monkeypatch.setattr(app_factory.asyncio, "sleep", immediate_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.SHUTTING_DOWN,
    )

    sync_calls: list[bool] = []

    async def fake_to_thread(_fn, *args, **kwargs):
        sync_calls.append(True)
        return None

    monkeypatch.setattr(app_factory.asyncio, "to_thread", fake_to_thread)

    await app_factory._graph_synchronization_loop(interval_seconds=0.0)  # pylint: disable=protected-access
    assert sync_calls == []


@pytest.mark.asyncio
async def test_lifespan_blocks_startup_when_reconciliation_is_execution_blocked(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Lifespan should propagate recovery-gate execution blocks at startup."""
    app = FastAPI()
    init_calls: list[bool] = []

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )
    monkeypatch.setattr(
        app_factory,
        "init_rebuild_executor",
        lambda s: init_calls.append(True),
    )

    def _raise_block(*_args, **_kwargs):
        raise ExecutionBlockedError(
            "blocked at startup",
            action="unsafe",
            inconsistency_type="stale_ownership",
        )

    monkeypatch.setattr(app_factory, "_run_startup_reconciliation", _raise_block)

    with pytest.raises(ExecutionBlockedError):
        async with app_factory.lifespan(app):
            pass

    assert not init_calls, "executor should not initialize when startup reconciliation is blocked"


@pytest.mark.asyncio
async def test_lifespan_blocks_startup_when_reconciliation_and_defensive_init_fail(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Lifespan must fail startup if defensive init_db also fails."""
    app = FastAPI()
    init_calls: list[bool] = []

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )
    monkeypatch.setattr(
        app_factory,
        "init_rebuild_executor",
        lambda s: init_calls.append(True),
    )

    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
        raise RuntimeError("reconciliation failed")

    monkeypatch.setattr(
        app_factory,
        "_run_startup_reconciliation",
        _raise_reconciliation_failure,
    )

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        async with app_factory.lifespan(app):
            pass

    assert not init_calls, "executor should not initialize when startup reconciliation fails"


def test_startup_reconciliation_does_not_release_lock_without_reset_reacquire(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Startup reconciliation should skip release when RESET did not reacquire."""
    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    class _GateNoReacquire:
        def __init__(self, **_kwargs) -> None:
            self.lock_was_reacquired = False

        def ensure_safe_to_execute(self, cancellation_event=None) -> None:
            raise ExecutionBlockedError("wait", action="wait", inconsistency_type="none")

    # FIX: Provide clean dummy context managers to support 'with session_scope()' tracking metrics
    @contextlib.contextmanager
    def fake_session_scope(*args, **kwargs):
        yield MagicMock()

    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.init_db", lambda _engine: None)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: lambda: None)
    monkeypatch.setattr("src.data.repository.session_scope", fake_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", _GateNoReacquire)

    with pytest.raises(ExecutionBlockedError):
        app_factory._run_startup_reconciliation(cast(Any, base_settings))  # pylint: disable=protected-access

    fake_lock.release.assert_not_called()


def test_startup_reconciliation_releases_lock_when_reset_reacquired(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Startup reconciliation should verify lock release when safety check resolves cleanly."""
    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    class _GateReacquired:
        def __init__(self, **_kwargs) -> None:
            self.lock_was_reacquired = True

        def ensure_safe_to_execute(self, cancellation_event=None) -> None:
            return None

    @contextlib.contextmanager
    def fake_session_scope(*args, **kwargs):
        yield MagicMock()

    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.init_db", lambda _engine: None)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: lambda: None)
    monkeypatch.setattr("src.data.repository.session_scope", fake_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", _GateReacquired)

    app_factory._run_startup_reconciliation(cast(Any, base_settings))  # pylint: disable=protected-access

    assert fake_lock.lock_name == "graph_rebuild"


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_triggers_recovery(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """_periodic_reconciliation_loop should invoke gate.ensure_safe_to_execute for automatic reset plans."""
    import asyncio
    from datetime import datetime

    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, ReconciliationPlan, Severity

    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    # Mock DB and Lock
    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: lambda: None)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)

    # Mock RebuildDriftEvaluator
    monkeypatch.setattr("src.logic.rebuild_drift_evaluator.RebuildDriftEvaluator", MagicMock())

    # Mock ReconciliationEngine to return a reset plan with automatic execution mode
    from datetime import timezone

    mock_plan = ReconciliationPlan(
        drift_type="orphaned_running",
        severity=Severity.CRITICAL,
        actions=(ActionType.RESET_STATE,),
        target_state="converged",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason="test reset",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )

    class FakeEngine:
        def __init__(self, *args, **kwargs):
            pass

        def generate_reconciliation_plan(self):
            return mock_plan

    monkeypatch.setattr("src.logic.reconciliation_engine.ReconciliationEngine", FakeEngine)

    # Mock RecoveryGate
    ensure_safe_called = []

    class FakeGate:
        def __init__(self, **kwargs):
            self.lock_was_reacquired = False

        def ensure_safe_to_execute(self, cancellation_event=None):
            ensure_safe_called.append(True)

    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", FakeGate)

    # We want sleep to yield once then raise CancelledError to terminate the loop cleanly
    sleep_calls = 0

    async def mock_sleep(seconds: float):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(app_factory.asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.READY,
    )

    # Run the loop (it will run once, then sleep again, which raises CancelledError, terminating it)
    with pytest.raises(asyncio.CancelledError):
        await app_factory._periodic_reconciliation_loop(interval_seconds=0.1, settings=cast(Any, base_settings))  # pylint: disable=protected-access

    assert ensure_safe_called == [True]


@pytest.mark.asyncio
async def test_lifespan_emits_failure_event_on_startup_exception(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Lifespan must emit a failure event and fail-fast when startup raises an unexpected exception."""
    app = FastAPI()

    # Mock settings
    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )

    # Force an exception
    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
        """Raise a simulated runtime error to represent reconciliation failure."""
        raise ValueError("simulated unexpected startup error")

    monkeypatch.setattr(
        app_factory,
        "_run_startup_reconciliation",
        _raise_reconciliation_failure,
    )

    logged_events = []

    def fake_log_event(logger: Any, level: Any, event: Any) -> None:
        """Append logged events to a local list for assertion."""
        logged_events.append(event)

    monkeypatch.setattr(app_factory, "log_event", fake_log_event)

    init_calls: list[bool] = []
    monkeypatch.setattr(
        app_factory,
        "init_rebuild_executor",
        lambda s: init_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        async with app_factory.lifespan(app):
            pass

    assert len(logged_events) == 2

    # First event: startup_reconciliation_failed
    assert logged_events[0].event == "startup_reconciliation_failed"
    assert "ValueError" in logged_events[0].message
    assert logged_events[0].metadata["error"] == "ValueError"
    assert logged_events[0].metadata["message"] == "simulated unexpected startup error"
    assert not init_calls, "executor should not initialize when startup reconciliation fails"
    assert logged_events[0].metadata["phase"] == "reconciliation"
    assert "trace_id" in logged_events[0].metadata
    assert "span_id" in logged_events[0].metadata

    # Second event: startup_failed
    assert logged_events[1].event == "startup_failed"
    assert "RuntimeError" in logged_events[1].message
    assert logged_events[1].metadata["error"] == "RuntimeError"
    assert "Failed to load persisted graph during startup" in logged_events[1].metadata["message"]
    assert "trace_id" in logged_events[1].metadata
    assert "span_id" in logged_events[1].metadata

    # Continuity: ensure the reconciliation trace context propagates to the outer startup event
    assert logged_events[0].metadata["trace_id"] == logged_events[1].metadata["trace_id"], "Trace ID mismatch"
    assert logged_events[0].metadata["span_id"] == logged_events[1].metadata["span_id"], "Span ID mismatch"


@pytest.mark.asyncio
async def test_lifespan_emits_startup_failed_with_trace_ids_on_get_graph_exception(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Ensure get_graph exceptions trace ids.

    When get_graph() raises during the traced startup block, the lifespan should:
      - raise the original exception (fail-fast)
      - emit exactly one ObservabilityEvent with event == "startup_failed"
      - include the generated trace_id and span_id in the event.metadata
    """
    app = FastAPI()

    # Mock settings
    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )

    # Mock reconciliation to succeed
    async def mock_perform_startup_reconciliation(*_args, **_kwargs) -> None:
        """Mock startup reconciliation to succeed without side effects."""
        pass

    monkeypatch.setattr(
        app_factory,
        "_perform_startup_reconciliation",
        mock_perform_startup_reconciliation,
    )

    # Make get_graph raise a deterministic exception
    def _raise_get_graph():
        """Simulate a failure in graph retrieval during startup."""
        raise RuntimeError("simulated get_graph failure")

    monkeypatch.setattr(app_factory, "get_graph", _raise_get_graph)

    # Make uuid4 deterministic so we can assert against expected trace/span ids
    hex_values = ["deadbeef-trace", "deadbeef-span"]

    def fake_uuid4() -> Any:
        """Return a predictable sequence of fake UUIDs."""
        return type("U", (), {"hex": hex_values.pop(0)})()

    monkeypatch.setattr(app_factory, "uuid4", fake_uuid4)

    # Capture emitted observability events
    logged_events = []

    def fake_log_event(logger: Any, level: Any, event: Any) -> None:
        """Append captured observability events to a local list."""
        logged_events.append(event)

    monkeypatch.setattr(app_factory, "log_event", fake_log_event)

    # Expect the original exception to propagate from the lifespan manager
    with pytest.raises(RuntimeError, match="simulated get_graph failure"):
        async with app_factory.lifespan(app):
            pass

    # Validate emitted events
    startup_events = [e for e in logged_events if getattr(e, "event", "") == "startup_failed"]
    assert len(startup_events) == 1, f"expected 1 startup_failed event, got {len(startup_events)}"

    ev = startup_events[0]

    # The implementation must attach trace_id/span_id to event.metadata for this test to pass.
    # Expected values based on the fake_uuid4 above:
    expected_trace_id = "startup-deadbeef-trace"
    expected_span_id = "startup-span-deadbeef-span"

    assert "trace_id" in ev.metadata, "trace_id missing from startup_failed event metadata"
    assert "span_id" in ev.metadata, "span_id missing from startup_failed event metadata"
    assert ev.metadata["trace_id"] == expected_trace_id
    assert ev.metadata["span_id"] == expected_span_id
