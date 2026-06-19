"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from api import app_factory
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
        """Mock shutdown procedure."""
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
        """Mock sleep to return immediately."""
        future: asyncio.Future[None] = asyncio.Future()
        future.set_result(None)
        await future  # use async feature

    monkeypatch.setattr(app_factory.asyncio, "sleep", immediate_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.SHUTTING_DOWN,
    )

    sync_calls: list[bool] = []

    async def fake_to_thread(_fn, *args, **kwargs):
        """Mock to_thread to capture calls."""
        future: asyncio.Future[None] = asyncio.Future()
        future.set_result(None)
        await future  # use async feature
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
        """Simulate an execution blocked error."""
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
        """Simulate a reconciliation failure."""
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


@pytest.mark.parametrize(
    "lock_reacquired, should_raise",
    [
        (False, True),
        (True, False),
        (True, True),
    ],
    ids=["no_reacquire_raises", "reacquired_releases", "reacquired_with_exception"],
)
def test_startup_reconciliation_lock_release_behavior(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
    lock_reacquired: bool,
    should_raise: bool,
) -> None:
    """Startup reconciliation lock release behavior based on reacquisition."""
    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    class _GateMock:
        """Mock RecoveryGate with parameterized reacquisition behavior."""

        def __init__(self, **_kwargs) -> None:
            self.lock_was_reacquired = lock_reacquired

        def ensure_safe_to_execute(self, cancellation_event=None) -> None:
            """Simulate blocking execution or passing."""
            if should_raise:
                raise ExecutionBlockedError("wait", action="wait", inconsistency_type="none")
            return None

    # FIX: Provide clean dummy context managers to support 'with session_scope()' tracking metrics
    @contextlib.contextmanager
    def fake_session_scope(*args, **kwargs):
        """Mock database session scope."""
        yield MagicMock()

    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.init_db", lambda _engine: None)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: lambda: None)
    monkeypatch.setattr("src.data.repository.session_scope", fake_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", _GateMock)

    if should_raise:
        with pytest.raises(ExecutionBlockedError):
            app_factory._run_startup_reconciliation(cast(Any, base_settings))  # pylint: disable=protected-access
        if lock_reacquired:
            assert fake_lock.lock_name == "graph_rebuild"
            fake_lock.release.assert_called()
        else:
            fake_lock.release.assert_not_called()
    else:
        app_factory._run_startup_reconciliation(cast(Any, base_settings))  # pylint: disable=protected-access
        assert fake_lock.lock_name == "graph_rebuild"
        fake_lock.release.assert_called()


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_triggers_recovery(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """_periodic_reconciliation_loop should invoke gate.ensure_safe_to_execute for automatic reset plans."""
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

    mock_plan = ReconciliationPlan(
        drift_type="orphaned_running",
        severity=Severity.CRITICAL,
        actions=(ActionType.RESET_STATE,),
        target_state="converged",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason="test reset",
        metadata={},
        created_at=datetime.now(UTC),
    )

    class FakeEngine:
        """Mock ReconciliationEngine."""

        def __init__(self, *args, **kwargs):
            """Accept arguments."""

        def generate_reconciliation_plan(self):
            """Return a mock reconciliation plan."""
            return mock_plan

    monkeypatch.setattr("src.logic.reconciliation_engine.ReconciliationEngine", FakeEngine)

    # Mock RecoveryGate
    ensure_safe_called = []

    class FakeGate:
        """Mock RecoveryGate."""

        def __init__(self, **kwargs):
            self.lock_was_reacquired = False

        def ensure_safe_to_execute(self, cancellation_event=None):
            """Track that ensure_safe_to_execute was called."""
            ensure_safe_called.append(True)

    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", FakeGate)

    # We want sleep to yield once then raise CancelledError to terminate the loop cleanly
    sleep_calls = 0

    async def mock_sleep(seconds: float):
        """Mock sleep to yield once then raise CancelledError."""
        future: asyncio.Future[None] = asyncio.Future()
        future.set_result(None)
        await future  # use async feature
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("src.logic.reconciliation_loop.asyncio.sleep", mock_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.READY,
    )

    # Run the loop (it will run once, then sleep again, which raises CancelledError, terminating it)
    with pytest.raises(asyncio.CancelledError):
        from src.logic.reconciliation_loop import periodic_reconciliation_loop

        async def fake_run_with_trace(fn, **kwargs):
            """Mock run_with_trace function."""
            future: asyncio.Future[None] = asyncio.Future()
            future.set_result(None)
            await future
            return fn()

        await periodic_reconciliation_loop(
            interval_seconds=0.1,
            database_url=base_settings.database_url,
            is_shutdown_fn=lambda: False,
            run_with_trace_fn=fake_run_with_trace,
            coordination_database_url=base_settings.database_url,
            cancel_event=None,
            lock_ttl_seconds=300,
        )

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

    # Mock _run_startup_reconciliation because it is the underlying synchronous
    # function dispatched via asyncio.to_thread in _perform_startup_reconciliation.
    # Monkeypatching this target specifically ensures we test the context/thread
    # propagation boundary while properly executing and validating the exact
    # `log_event` logic enclosed within `_perform_startup_reconciliation`'s error handling.
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
        await asyncio.sleep(0)  # use async feature

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

    # Make trace IDs deterministic so we can assert against expected values
    def fake_generate_trace_ids() -> tuple[str, str]:
        """Return a predictable sequence of trace IDs."""
        return "startup-deadbeef-trace", "startup-span-deadbeef-span"

    monkeypatch.setattr(app_factory, "_generate_startup_trace_ids", fake_generate_trace_ids)

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


@pytest.mark.asyncio
async def test_tracing_context_does_not_leak_into_background_tasks(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Verify that tracing context from startup does not leak into background tasks."""
    app = FastAPI()

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: base_settings,
    )

    # Mock reconciliation to succeed
    async def mock_perform_startup_reconciliation(*_args, **_kwargs) -> None:
        """Mock startup reconciliation to succeed without side effects."""
        await asyncio.sleep(0)  # use async feature

    monkeypatch.setattr(
        app_factory,
        "_perform_startup_reconciliation",
        mock_perform_startup_reconciliation,
    )

    # Mock get_graph to succeed
    monkeypatch.setattr(app_factory, "get_graph", lambda: None)

    tasks: list[asyncio.Task] = []

    def fake_start_background_tasks(
        has_persistence: bool, settings: Any
    ) -> tuple[asyncio.Task, asyncio.Task, asyncio.Task]:
        """Mock spawning of background tasks."""
        from src.observability.context import get_trace_id

        async def fake_task():
            """Return the active trace context if any."""
            await asyncio.sleep(0)  # use async feature
            return get_trace_id()

        t1, t2, t3 = (
            asyncio.create_task(fake_task()),
            asyncio.create_task(fake_task()),
            asyncio.create_task(fake_task()),
        )
        tasks.extend([t1, t2, t3])
        return t1, t2, t3

    monkeypatch.setattr(app_factory, "_start_background_tasks", fake_start_background_tasks)

    # Mock _perform_orderly_shutdown
    async def fake_shutdown(*_args, **_kwargs):
        """Mock shutdown procedure."""
        await asyncio.sleep(0)  # use async feature

    monkeypatch.setattr(app_factory, "_perform_orderly_shutdown", fake_shutdown)

    async with app_factory.lifespan(app):
        pass

    assert len(tasks) == 3, "Expected 3 background tasks to be created"
    results = await asyncio.gather(*tasks)

    assert all(r is None for r in results), "Trace context leaked into background task"


def test_generate_startup_trace_ids_format() -> None:
    """Verify that _generate_startup_trace_ids produces valid W3C-compatible trace and span IDs."""
    from api.app_factory import _generate_startup_trace_ids

    trace_id, span_id = _generate_startup_trace_ids()

    # Trace ID should be 32 hex chars
    assert len(trace_id) == 32
    assert all(c in "0123456789abcdef" for c in trace_id)

    # Span ID should be 16 hex chars
    assert len(span_id) == 16
    assert all(c in "0123456789abcdef" for c in span_id)
