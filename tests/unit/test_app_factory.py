"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from api import app_factory
from src.config.settings import DeploymentEnvironment
from src.data.database import SchemaCompatibilityError
from src.data.sample_data import create_sample_database
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
    monkeypatch.setattr(app_factory, "get_graph", lambda: None)
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

    monkeypatch.setattr(app_factory, "_perform_startup_reconciliation", _raise_reconciliation_failure)

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        async with app_factory.lifespan(app):
            pass

    assert not init_calls, "executor should not initialize when startup reconciliation fails"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reconciliation_fails", "bootstrap_fails", "expected_phase"),
    [
        (True, False, "reconciliation"),
        (False, True, "graph_bootstrap"),
    ],
    ids=["reconciliation-failure", "graph-bootstrap-failure"],
)
async def test_lifespan_allows_hosted_fallback_startup_failures_to_boot(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
    reconciliation_fails: bool,
    bootstrap_fails: bool,
    expected_phase: str,
) -> None:
    """Hosted fallback startup should degrade instead of crashing the app on reconciliation or bootstrap failures."""
    app = FastAPI()
    hosted_settings = SimpleNamespace(
        **vars(base_settings),
        env=DeploymentEnvironment.PREVIEW,
        vercel_env="preview",
    )

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: hosted_settings,
    )

    if reconciliation_fails:

        def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
            """Mock a failed reconciliation attempt by raising an error."""
            raise OSError("reconciliation failed")

        monkeypatch.setattr(app_factory, "_perform_startup_reconciliation", _raise_reconciliation_failure)
    else:

        async def _async_noop(*_args, **_kwargs) -> None:
            """Mock a successful startup reconciliation call by doing nothing (no-op)."""

        monkeypatch.setattr(app_factory, "_perform_startup_reconciliation", _async_noop)

    if bootstrap_fails:

        def _raise_bootstrap_failure(*_args, **_kwargs) -> Any:
            """Mock a failed graph bootstrap by raising an error."""
            raise OSError("graph bootstrap failed")

        monkeypatch.setattr(app_factory, "get_graph", _raise_bootstrap_failure)
    else:
        monkeypatch.setattr(app_factory, "get_graph", create_sample_database)

    background_task = asyncio.create_task(asyncio.sleep(0))
    monkeypatch.setattr(
        app_factory,
        "_start_background_tasks",
        lambda has_persistence, settings: (None, background_task, None),
    )
    monkeypatch.setattr(app_factory, "shutdown_rebuild_executor", lambda: None)

    logged_events: list[Any] = []

    def fake_log_event(_logger: Any, _level: Any, event: Any) -> None:
        """Capture structured startup events for assertion."""
        logged_events.append(event)

    monkeypatch.setattr(app_factory, "log_event", fake_log_event)

    async with app_factory.lifespan(app):
        pass

    assert any(
        getattr(event, "event", "") == "startup_degraded"
        and getattr(event, "metadata", {}).get("phase") == expected_phase
        for event in logged_events
    )


@pytest.mark.asyncio
async def test_lifespan_keeps_fail_fast_behavior_outside_hosted_fallback(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Non-hosted startup should still fail fast on reconciliation errors."""
    app = FastAPI()
    strict_settings = SimpleNamespace(
        **vars(base_settings),
        env=DeploymentEnvironment.DEVELOPMENT,
        vercel_env=None,
    )

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: strict_settings,
    )

    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
        """Simulate a startup reconciliation failure."""
        raise RuntimeError("reconciliation failed")

    monkeypatch.setattr(app_factory, "_perform_startup_reconciliation", _raise_reconciliation_failure)

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        async with app_factory.lifespan(app):
            pass


@pytest.mark.asyncio
async def test_hosted_fallback_cannot_degrade_schema_incompatibility(base_settings: SimpleNamespace) -> None:
    """Schema incompatibility must fail closed even where transient failures may degrade."""
    hosted_settings = SimpleNamespace(
        **vars(base_settings),
        env=DeploymentEnvironment.PREVIEW,
        vercel_env="preview",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            app_factory,
            "_verify_auth_database",
            lambda _guard: (_ for _ in ()).throw(SchemaCompatibilityError("incompatible auth schema")),
        )
        settings = cast(Any, hosted_settings)
        with pytest.raises(SchemaCompatibilityError, match="incompatible auth schema"):
            await app_factory._initialize_application_state(  # pylint: disable=protected-access
                settings,
                has_persistence=True,
                hosted_startup_degradation_allowed=True,
            )


@pytest.mark.asyncio
async def test_auth_database_verification_timeout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """A stalled auth catalog read must cancel its connection and shut down."""
    started = threading.Event()
    released = threading.Event()
    connection = MagicMock()
    connection.cancel.side_effect = released.set

    def _stalled_query(operation_guard) -> None:
        """Block one worker-owned connection until the outer guard cancels it."""
        operation_guard.register(connection)
        started.set()
        try:
            released.wait(timeout=1)
        finally:
            operation_guard.unregister(connection)

    monkeypatch.setattr(app_factory, "_verify_auth_database", _stalled_query)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_VERIFICATION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_SHUTDOWN_TIMEOUT_SECONDS", 0.5)
    wait_for = asyncio.wait_for

    async def _wait_after_connection_registration(awaitable, *, timeout):
        """Start the timeout only after the worker has registered its connection."""
        assert await asyncio.to_thread(started.wait, 1)
        return await wait_for(awaitable, timeout=timeout)

    monkeypatch.setattr(app_factory.asyncio, "wait_for", _wait_after_connection_registration)

    settings = cast(Any, base_settings)
    with pytest.raises(SchemaCompatibilityError, match="verification timed out"):
        await app_factory._initialize_application_state(  # pylint: disable=protected-access
            settings,
            has_persistence=False,
            hosted_startup_degradation_allowed=False,
        )

    assert started.is_set()
    assert released.is_set()
    connection.cancel.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_auth_database_verification_cancellation_closes_connection(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """Startup cancellation must stop and drain a shielded auth verification."""
    started = threading.Event()
    released = threading.Event()
    connection = MagicMock()
    connection.cancel.side_effect = released.set

    def _stalled_query(operation_guard) -> None:
        """Block one worker-owned connection until startup cancellation closes it."""
        operation_guard.register(connection)
        started.set()
        try:
            released.wait(timeout=1)
        finally:
            operation_guard.unregister(connection)

    monkeypatch.setattr(app_factory, "_verify_auth_database", _stalled_query)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_SHUTDOWN_TIMEOUT_SECONDS", 0.5)

    settings = cast(Any, base_settings)
    initialization = asyncio.create_task(
        app_factory._initialize_application_state(  # pylint: disable=protected-access
            settings,
            has_persistence=False,
            hosted_startup_degradation_allowed=False,
        )
    )
    assert await asyncio.to_thread(started.wait, 1)
    initialization.cancel()

    with pytest.raises(asyncio.CancelledError):
        await initialization

    assert released.is_set()
    connection.cancel.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_auth_database_verification_timeout_consumes_late_failure(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
) -> None:
    """A verification that outlives bounded shutdown must have its eventual failure retrieved."""
    started = threading.Event()
    release_failure = threading.Event()
    finished = threading.Event()
    consumed = threading.Event()
    connection = MagicMock()

    def _stalled_query(operation_guard) -> None:
        """Ignore connection cancellation until the test releases a late worker failure."""
        operation_guard.register(connection)
        started.set()
        try:
            release_failure.wait(timeout=1)
            raise RuntimeError("late verification failure")
        finally:
            operation_guard.unregister(connection)
            finished.set()

    original_consume = app_factory._consume_auth_database_verification_result

    def _consume_result(*args, **kwargs):
        """Record deterministic completion after retrieving the late task result."""
        try:
            return original_consume(*args, **kwargs)
        finally:
            consumed.set()

    consume_result = MagicMock(side_effect=_consume_result)
    monkeypatch.setattr(app_factory, "_verify_auth_database", _stalled_query)
    monkeypatch.setattr(app_factory, "_consume_auth_database_verification_result", consume_result)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_VERIFICATION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(app_factory, "_AUTH_DATABASE_SHUTDOWN_TIMEOUT_SECONDS", 0)
    wait_for = asyncio.wait_for

    async def _wait_after_connection_registration(awaitable, *, timeout):
        """Start the timeout only after the worker has registered its connection."""
        assert await asyncio.to_thread(started.wait, 1)
        return await wait_for(awaitable, timeout=timeout)

    monkeypatch.setattr(app_factory.asyncio, "wait_for", _wait_after_connection_registration)

    settings = cast(Any, base_settings)
    with pytest.raises(SchemaCompatibilityError, match="verification timed out"):
        await app_factory._initialize_application_state(  # pylint: disable=protected-access
            settings,
            has_persistence=False,
            hosted_startup_degradation_allowed=False,
        )

    release_failure.set()
    assert await asyncio.to_thread(finished.wait, 1)
    assert await asyncio.to_thread(consumed.wait, 1)

    consume_result.assert_called_once()


def test_auth_runtime_verification_does_not_call_mutators(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth startup verification must not create schema or seed credentials."""
    import api.auth as auth
    import api.database as database

    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr(database, "verify_schema_compatibility", verify_schema)
    monkeypatch.setattr(database, "verify_runtime_authority", verify_authority)
    monkeypatch.setattr(auth.user_repository, "has_users", lambda: True)
    initialize = MagicMock(side_effect=AssertionError("runtime DDL forbidden"))
    seed = MagicMock(side_effect=AssertionError("runtime credential seed forbidden"))
    monkeypatch.setattr(database, "initialize_schema", initialize)
    monkeypatch.setattr(auth, "seed_credentials_from_settings", seed)

    app_factory._verify_auth_database()  # pylint: disable=protected-access

    verify_schema.assert_called_once_with()
    verify_authority.assert_called_once_with()
    initialize.assert_not_called()
    seed.assert_not_called()


def test_auth_runtime_verification_sanitizes_unexpected_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Driver details must not escape the auth startup verification boundary."""
    import api.database as database

    monkeypatch.setattr(
        database,
        "verify_schema_compatibility",
        MagicMock(side_effect=OSError("credential-bearing driver detail")),
    )

    with pytest.raises(SchemaCompatibilityError, match=r"failed \(OSError\)") as exc_info:
        app_factory._verify_auth_database()  # pylint: disable=protected-access

    assert "credential-bearing" not in str(exc_info.value)


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
    from tests.unit.test_postgresql_topology import identity_engine

    fake_engine = identity_engine()
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
    monkeypatch.setattr("src.data.database.verify_database_schema", lambda _engine, **_kwargs: None)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", lambda _engine, **_kwargs: None)
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


def test_reconciliation_schema_verification_separates_runtime_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separate graph and coordination URLs must require disjoint capability roles."""
    from tests.unit.test_postgresql_topology import identity_engine

    graph_engine = identity_engine()
    coordination_engine = identity_engine(identifier="99999")
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)

    app_factory._verify_reconciliation_schemas(  # pylint: disable=protected-access
        graph_engine,
        coordination_engine,
    )

    assert verify_schema.call_args_list[0].args == (graph_engine,)
    assert verify_schema.call_args_list[0].kwargs["required_capabilities"] == {"graph"}
    assert verify_schema.call_args_list[1].args == (coordination_engine,)
    assert verify_schema.call_args_list[1].kwargs["required_capabilities"] == {"coordination"}
    assert verify_authority.call_args_list[0].kwargs["required_capabilities"] == {"graph"}
    assert verify_authority.call_args_list[1].kwargs["required_capabilities"] == {"coordination"}


@pytest.mark.asyncio
async def test_periodic_reconciliation_loop_triggers_recovery(
    monkeypatch: pytest.MonkeyPatch,
    base_settings: SimpleNamespace,
    make_reconciliation_plan,
) -> None:
    """periodic_reconciliation_loop should retrieve and consume automatic reset reconciliation plans."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode, ExecutionSafety, Severity
    from tests.unit.test_postgresql_topology import identity_engine

    fake_engine = identity_engine()
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    # Mock DB and Lock
    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: lambda: None)
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)

    # Mock RebuildDriftEvaluator
    monkeypatch.setattr("src.logic.rebuild_drift_evaluator.RebuildDriftEvaluator", MagicMock())

    # Mock ReconciliationEngine to return a reset plan with automatic execution mode
    mock_plan = make_reconciliation_plan(
        drift_type="orphaned_running",
        severity=Severity.CRITICAL,
        actions=(ActionType.RESET_STATE,),
        target_state="converged",
        execution_mode=ExecutionMode.AUTOMATIC,
        safety_state=ExecutionSafety.RESET_REQUIRED,
        reason="test reset",
    )

    fake_engine_inst = MagicMock()
    fake_engine_inst.generate_reconciliation_plan.return_value = mock_plan
    monkeypatch.setattr(
        "src.logic.reconciliation_engine.ReconciliationEngine", MagicMock(return_value=fake_engine_inst)
    )

    # Mock RecoveryGate
    consume_plan_called = []
    fake_gate = MagicMock()
    fake_gate.lock_was_reacquired = False
    fake_gate.get_reconciliation_plan.return_value = mock_plan
    fake_gate.consume_reconciliation_plan.side_effect = lambda plan, cancellation_event=None: (
        consume_plan_called.append(True)
    )
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", MagicMock(return_value=fake_gate))

    # We want sleep to yield once then raise CancelledError to terminate the loop cleanly
    sleep_calls = 0

    original_sleep = asyncio.sleep

    async def mock_sleep(seconds: float):
        """Mock sleep to yield once then raise CancelledError."""
        await original_sleep(0)
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
            """Run the traced callable and return an awaitable result."""
            await original_sleep(0)
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

    assert consume_plan_called == [True]


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


def _assert_start_background_tasks_lock_ttl(monkeypatch, configured_ttl: int, expected_ttl: int) -> None:
    """Assert periodic reconciliation receives the bounded rebuild lock TTL."""
    settings = SimpleNamespace(
        database_url="sqlite:///:memory:",
        coordination_database_url="sqlite:///:memory:",
        graph_sync_interval_seconds=60.0,
        reconciliation_interval_seconds=30.0,
        rebuild_lock_ttl_seconds=configured_ttl,
    )

    recon_loop_mock = MagicMock()
    monkeypatch.setattr("src.logic.reconciliation_loop.periodic_reconciliation_loop", recon_loop_mock)
    monkeypatch.setattr("api.app_factory.init_rebuild_executor", lambda s: None)
    monkeypatch.setattr("api.app_factory._graph_synchronization_loop", lambda interval_seconds: None)
    monkeypatch.setattr("api.app_factory._slo_evaluation_loop", lambda: None)
    monkeypatch.setattr("api.app_factory._resolve_startup_reconciliation_url", lambda s: "sqlite:///:memory:")

    create_task_mock = MagicMock()
    monkeypatch.setattr("api.app_factory.asyncio.create_task", create_task_mock)

    from api.app_factory import _start_background_tasks

    _start_background_tasks(has_persistence=True, settings=cast(Any, settings))

    recon_loop_mock.assert_called_once()
    assert recon_loop_mock.call_args[1]["lock_ttl_seconds"] == expected_ttl


def test_start_background_tasks_propagates_rebuild_lock_ttl_seconds(monkeypatch) -> None:
    """_start_background_tasks should propagate settings.rebuild_lock_ttl_seconds to periodic_reconciliation_loop."""
    _assert_start_background_tasks_lock_ttl(monkeypatch, configured_ttl=120, expected_ttl=120)


def test_start_background_tasks_caps_rebuild_lock_ttl_seconds(monkeypatch) -> None:
    """_start_background_tasks should cap periodic reconciliation lock TTL at the distributed-lock limit."""
    _assert_start_background_tasks_lock_ttl(monkeypatch, configured_ttl=450, expected_ttl=300)


def test_start_background_tasks_floors_rebuild_lock_ttl_seconds(monkeypatch) -> None:
    """_start_background_tasks should floor periodic reconciliation lock TTL at one second."""
    _assert_start_background_tasks_lock_ttl(monkeypatch, configured_ttl=0, expected_ttl=1)


def test_authoritative_graph_unavailable_returns_503() -> None:
    """AuthoritativeGraphUnavailableError must be mapped to HTTP 503."""
    from fastapi.testclient import TestClient

    from api.app_factory import create_app
    from api.graph_lifecycle_providers import AuthoritativeGraphUnavailableError

    test_app = create_app()

    @test_app.get("/test-graph-unavailable")
    def _trigger_unavailable():
        """Provide trigger unavailable for this regression."""
        raise AuthoritativeGraphUnavailableError("Graph not yet published")

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/test-graph-unavailable")
    assert response.status_code == 503
    assert response.json() == {"detail": "Graph not yet published; awaiting initial rebuild."}


def test_reconciliation_blocked_clean_install_requires_zero_jobs(monkeypatch) -> None:
    """_handle_reconciliation_blocked must require independent evidence (zero rebuild jobs or quiescent state)."""
    from api.app_factory import _handle_reconciliation_blocked

    exc = ExecutionBlockedError("waiting", action="wait", inconsistency_type="none")
    dummy_settings = MagicMock()
    monkeypatch.setattr("api.app_factory._has_never_published_graph", lambda s: False)

    # Case 1: Genuine clean install (zero rebuild jobs) -> returns True
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: True)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: False)
    assert _handle_reconciliation_blocked(exc, dummy_settings) is True

    # Case 2: Established deployment with terminal latest job (quiescent restart) -> returns False
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: False)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: True)
    assert _handle_reconciliation_blocked(exc, dummy_settings) is False

    # Case 3: Established deployment with active/non-terminal job -> fails closed and raises
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: False)
    with pytest.raises(ExecutionBlockedError):
        _handle_reconciliation_blocked(exc, dummy_settings)

    # Case 4a: Non-wait action with benign inconsistency -> fails closed regardless of clean/quiescent state
    exc_non_wait = ExecutionBlockedError("non-wait", action="resume", inconsistency_type="none")
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: True)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: True)
    with pytest.raises(ExecutionBlockedError):
        _handle_reconciliation_blocked(exc_non_wait, dummy_settings)

    # Case 4b: Wait action with drift inconsistency -> fails closed regardless of clean/quiescent state
    exc_drift = ExecutionBlockedError("drift", action="wait", inconsistency_type="orphaned_running")
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: True)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: True)
    with pytest.raises(ExecutionBlockedError):
        _handle_reconciliation_blocked(exc_drift, dummy_settings)

    # Case 4c: Non-wait action with drift inconsistency -> fails closed regardless of clean/quiescent state
    exc_both = ExecutionBlockedError("both", action="resume", inconsistency_type="orphaned_running")
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: True)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: True)
    with pytest.raises(ExecutionBlockedError):
        _handle_reconciliation_blocked(exc_both, dummy_settings)


def test_reconciliation_blocked_never_published_graph_allows_empty_startup(monkeypatch) -> None:
    """A verified history with no published graph (failed/cancelled first rebuild) may start without a graph."""
    from api.app_factory import _handle_reconciliation_blocked

    exc = ExecutionBlockedError("waiting", action="wait", inconsistency_type="none")
    monkeypatch.setattr("api.app_factory._is_genuine_clean_install", lambda s: False)
    monkeypatch.setattr("api.app_factory._has_never_published_graph", lambda s: True)
    monkeypatch.setattr("api.app_factory._is_quiescent_established_state", lambda s: True)
    assert _handle_reconciliation_blocked(exc, MagicMock()) is True

    # Without that proof the established quiescent path keeps requiring a published graph.
    monkeypatch.setattr("api.app_factory._has_never_published_graph", lambda s: False)
    assert _handle_reconciliation_blocked(exc, MagicMock()) is False

    # The allowance never applies to non-benign blocks.
    monkeypatch.setattr("api.app_factory._has_never_published_graph", lambda s: True)
    for blocked in (
        ExecutionBlockedError("drift", action="wait", inconsistency_type="orphaned_running"),
        ExecutionBlockedError("resume", action="resume", inconsistency_type="none"),
    ):
        settings = MagicMock()
        with pytest.raises(ExecutionBlockedError):
            _handle_reconciliation_blocked(blocked, settings)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], False),
        (["failed"], True),
        (["cancelled"], True),
        (["failed", "cancelled"], True),
        (["succeeded"], False),
        (["succeeded", "failed"], False),
        (["failed", "succeeded"], False),
        (["failed", "pending"], False),
        (["failed", "running"], False),
    ],
)
def test_has_never_published_graph_uses_rebuild_history(tmp_path, statuses, expected) -> None:
    """Only a failed/cancelled latest job with no successful job proves that nothing was ever published."""
    from datetime import datetime, timedelta, timezone

    from src.data.database import create_engine_from_url, create_session_factory, init_db
    from src.data.db_models import RebuildJobORM, RebuildJobStatus
    from src.data.repository import AssetGraphRepository, session_scope

    url = f"sqlite:///{tmp_path / 'history.db'}"
    engine = create_engine_from_url(url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            for offset, status in enumerate(statuses):
                job_id = repo.create_rebuild_job(requested_by="tester")
                job = session.get(RebuildJobORM, job_id)
                assert job is not None
                job.status = RebuildJobStatus(status)
                job.created_at = base + timedelta(minutes=offset)
                job.completed_at = base + timedelta(minutes=offset, seconds=30)
    finally:
        engine.dispose()

    settings = SimpleNamespace(database_url=url, has_durable_graph_persistence=True)
    assert app_factory._has_never_published_graph(cast(Any, settings)) is expected


def test_has_never_published_graph_fails_closed_when_store_unreadable() -> None:
    """Verification errors must never be read as proof that no graph was published."""
    settings = SimpleNamespace(database_url=None, has_durable_graph_persistence=True)
    assert app_factory._has_never_published_graph(cast(Any, settings)) is False


@pytest.mark.asyncio
async def test_blocked_reconciliation_verification_does_not_block_event_loop(monkeypatch) -> None:
    """Blocked-state database verification must run off the event loop thread."""
    import time

    def _raise_block(*_args, **_kwargs):
        """Simulate a benign blocked reconciliation result."""
        raise ExecutionBlockedError("waiting", action="wait", inconsistency_type="none")

    def _slow_handler(_exc, _settings) -> bool:
        """Simulate synchronous database verification taking time."""
        time.sleep(0.4)
        return True

    monkeypatch.setattr(app_factory, "_run_startup_reconciliation", _raise_block)
    monkeypatch.setattr(app_factory, "_handle_reconciliation_blocked", _slow_handler)

    max_gap = 0.0
    stop = asyncio.Event()

    async def _ticker() -> None:
        """Measure event loop responsiveness during verification."""
        nonlocal max_gap
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            max_gap = max(max_gap, now - last)
            last = now

    ticker = asyncio.create_task(_ticker())
    await asyncio.sleep(0.05)  # let the ticker establish a baseline before startup work begins
    try:
        result = await app_factory._perform_startup_reconciliation(cast(Any, MagicMock()))
        await asyncio.sleep(0.05)  # let the ticker observe any stall caused by the verification
    finally:
        stop.set()
        await ticker

    assert result is True
    assert max_gap < 0.2, f"event loop was blocked for {max_gap:.3f}s"


@pytest.mark.asyncio
async def test_blocked_reconciliation_verification_is_time_bounded(monkeypatch) -> None:
    """A stuck blocked-state verification must fail startup instead of hanging it."""
    import time

    def _raise_block(*_args, **_kwargs):
        """Simulate a benign blocked reconciliation result."""
        raise ExecutionBlockedError("waiting", action="wait", inconsistency_type="none")

    def _slow_handler(_exc, _settings) -> bool:
        """Simulate verification that exceeds the startup timeout."""
        time.sleep(0.3)
        return True

    monkeypatch.setattr(app_factory, "_run_startup_reconciliation", _raise_block)
    monkeypatch.setattr(app_factory, "_handle_reconciliation_blocked", _slow_handler)
    monkeypatch.setattr(app_factory, "_STARTUP_BLOCKED_VERIFICATION_TIMEOUT_SECONDS", 0.05)

    settings = cast(Any, MagicMock())
    with pytest.raises(RuntimeError, match="timed out"):
        await app_factory._perform_startup_reconciliation(settings)


@pytest.mark.parametrize(
    "path",
    [
        "/api/assets",
        "/api/assets/ANY",
        "/api/assets/ANY/relationships",
        "/api/relationships",
        "/api/graph/metrics",
        "/api/visualization",
    ],
)
def test_graph_read_routes_return_503_when_no_graph_is_published(monkeypatch, path) -> None:
    """Empty-store startup must surface 503 (pending publication), not a masked generic 500."""
    from fastapi.testclient import TestClient

    from api import graph_lifecycle
    from api.graph_lifecycle_providers import AuthoritativeGraphUnavailableError

    def _no_graph():
        """Simulate an authoritative store awaiting first publication."""
        raise AuthoritativeGraphUnavailableError("No authoritative published graph found in persistent storage.")

    graph_lifecycle.reset_graph()
    monkeypatch.setattr(graph_lifecycle, "initialize_graph_runtime", _no_graph)
    try:
        client = TestClient(app_factory.create_app(), raise_server_exceptions=False)
        response = client.get(path)
    finally:
        graph_lifecycle.reset_graph()

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph not yet published; awaiting initial rebuild."}


def test_graph_read_during_first_rebuild_returns_503_and_preserves_rebuilding_state() -> None:
    """A read before the first publication must stay a typed 503 and never disturb the REBUILDING lifecycle state."""
    from fastapi.testclient import TestClient

    from api import graph_lifecycle

    graph_lifecycle.reset_graph()
    try:
        graph_lifecycle.begin_rebuild()
        client = TestClient(app_factory.create_app(), raise_server_exceptions=False)
        response = client.get("/api/assets")

        assert response.status_code == 503
        assert graph_lifecycle.get_runtime_lifecycle_state() == graph_lifecycle.GraphRuntimeLifecycleState.REBUILDING
    finally:
        graph_lifecycle.reset_graph()


@pytest.mark.parametrize("same_login", [True, False])
def test_reconciliation_same_database_distinct_sessions_capabilities(monkeypatch, same_login) -> None:
    """Combined requirements apply only to identity-proved same-database shared logins."""
    from tests.unit.test_postgresql_topology import identity_engine

    graph_engine = identity_engine()
    coordination_engine = identity_engine()
    graph_engine.identity_connections[0].execute.return_value.scalar_one.return_value = "graph_login"
    coordination_engine.identity_connections[0].execute.return_value.scalar_one.return_value = (
        "graph_login" if same_login else "coordination_login"
    )
    verify_schema = MagicMock()
    verify_authority = MagicMock()
    monkeypatch.setattr("src.data.database.verify_database_schema", verify_schema)
    monkeypatch.setattr("src.data.database.verify_runtime_database_authority", verify_authority)
    app_factory._verify_reconciliation_schemas(graph_engine, coordination_engine)
    expected = [{"graph", "coordination"}] * 2 if same_login else [{"graph"}, {"coordination"}]
    for verifier in (verify_schema, verify_authority):
        assert [call.kwargs["required_capabilities"] for call in verifier.call_args_list] == expected
        assert all(call.kwargs["combined_topology"] for call in verifier.call_args_list)
        assert verifier.call_args_list[0].kwargs["verification_connection"] is graph_engine.identity_connections[0]
        assert (
            verifier.call_args_list[1].kwargs["verification_connection"] is coordination_engine.identity_connections[0]
        )


@pytest.mark.asyncio
async def test_blocked_verification_cancels_owned_connection_and_observes_worker(monkeypatch) -> None:
    """Timeout cancels the actual worker connection rather than only its awaitable."""
    import threading

    finished = threading.Event()
    cancelled = threading.Event()
    connection = MagicMock()
    connection.cancel.side_effect = cancelled.set

    def blocked_handler(_exc, _settings):
        """Wait until the operation guard cancels this simulated database query."""
        operation = app_factory._BLOCKED_VERIFICATION.get()
        assert operation is not None
        operation.guard.register(connection)
        assert cancelled.wait(1)
        finished.set()
        return True

    monkeypatch.setattr(app_factory, "_handle_reconciliation_blocked", blocked_handler)
    monkeypatch.setattr(app_factory, "_STARTUP_BLOCKED_VERIFICATION_TIMEOUT_SECONDS", 0.02)
    with pytest.raises(RuntimeError, match="Startup reconciliation timed out"):
        await app_factory._handle_reconciliation_blocked_bounded(MagicMock(), MagicMock())
    assert finished.is_set()
    connection.cancel.assert_called_once()
    assert connection.close.called


def test_startup_evidence_postgres_connect_and_query_share_deadline(monkeypatch) -> None:
    """Driver limits and cancellation registration cover every retained evidence connection."""
    from sqlalchemy import create_engine

    engine = create_engine("postgresql://localhost/test")
    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: engine)
    operation = app_factory._BlockedVerification(10)
    token = app_factory._BLOCKED_VERIFICATION.set(operation)
    try:
        assert app_factory._create_startup_evidence_engine("postgresql://localhost/test") is engine
        params: dict[str, Any] = {}
        engine.dialect.dispatch.do_connect(engine.dialect, None, [], params)
        assert 1 <= params["connect_timeout"] <= 5
        assert "statement_timeout=" in params["options"]
        override = {"options": "-c statement_timeout=0"}
        with pytest.raises(SchemaCompatibilityError):
            engine.dialect.dispatch.do_connect(engine.dialect, None, [], override)
        cursor = MagicMock()
        engine.dispatch.before_cursor_execute(None, cursor, "SELECT 1", (), None, False)
        assert cursor.execute.call_args.args[0] == "SET statement_timeout = %s"
        assert 0 < cursor.execute.call_args.args[1][0] <= 10000
        operation.guard.cancel()
        connection = MagicMock()
        with pytest.raises(RuntimeError, match="cancelled"):
            list(engine.pool.dispatch.connect)[-1](connection, None)
        connection.close.assert_called_once()
    finally:
        app_factory._BLOCKED_VERIFICATION.reset(token)
        engine.dispose()


def test_expired_evidence_does_not_accept_late_success(monkeypatch) -> None:
    """Even a positive evidence result is rejected if it finishes after the deadline."""
    operation = app_factory._BlockedVerification(1)

    def late_handler(_exc, _settings):
        """Expire the operation before returning a positive result."""
        operation.deadline = 0
        return True

    monkeypatch.setattr(app_factory, "_handle_reconciliation_blocked", late_handler)
    with pytest.raises(TimeoutError):
        app_factory._run_blocked_verification(MagicMock(), MagicMock(), operation)
    assert app_factory._BLOCKED_VERIFICATION.get() is None


def test_sqlite_startup_evidence_query_is_interrupted_by_deadline() -> None:
    """Real SQLite work cannot continue past the evidence deadline."""
    import sqlite3

    from sqlalchemy.exc import OperationalError

    operation = app_factory._BlockedVerification(1)
    token = app_factory._BLOCKED_VERIFICATION.set(operation)
    engine = app_factory._create_startup_evidence_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            operation.deadline = 0
            with pytest.raises(OperationalError) as captured:
                connection.exec_driver_sql(
                    "WITH RECURSIVE counter(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM counter WHERE n<100000) "
                    "SELECT sum(n) FROM counter"
                )
            assert isinstance(captured.value.orig, sqlite3.OperationalError)
    finally:
        app_factory._BLOCKED_VERIFICATION.reset(token)
        engine.dispose()


def test_cancelled_startup_evidence_cannot_open_another_probe() -> None:
    """Cancellation prevents another evidence query even before the deadline expires."""
    operation = app_factory._BlockedVerification(30)
    operation.cancel()
    with pytest.raises(TimeoutError):
        operation.remaining()


def test_postgres_startup_evidence_real_deadline_and_cancellation() -> None:
    """A harness-owned PostgreSQL query stops on deadline and cannot be reused after cancellation."""
    import os
    import time

    from sqlalchemy.exc import DBAPIError

    from tests.integration.postgresql_disposable_cluster import URL_ENV, attested_connection

    database_url = os.environ.get(URL_ENV)
    if not database_url:
        pytest.skip("requires the fresh disposable PostgreSQL harness")
    assert database_url is not None
    with attested_connection(database_url):
        pass

    operation = app_factory._BlockedVerification(2)
    token = app_factory._BLOCKED_VERIFICATION.set(operation)
    engine = app_factory._create_startup_evidence_engine(database_url)
    try:
        started = time.monotonic()
        with pytest.raises(DBAPIError):
            with engine.connect() as connection:
                connection.exec_driver_sql("SELECT pg_sleep(8)")
        assert time.monotonic() - started < 7
        operation.cancel()
        with pytest.raises(TimeoutError):
            operation.remaining()
        engine.dispose()
        with pytest.raises(TimeoutError):
            engine.connect()
    finally:
        operation.cancel()
        app_factory._BLOCKED_VERIFICATION.reset(token)
        engine.dispose()


def test_postgres_startup_evidence_rejects_real_options_override() -> None:
    """A connection option cannot disable the bounded evidence query on the disposable target."""
    import os
    from urllib.parse import quote

    from tests.integration.postgresql_disposable_cluster import URL_ENV, attested_connection

    database_url = os.environ.get(URL_ENV)
    if not database_url:
        pytest.skip("requires the fresh disposable PostgreSQL harness")
    assert database_url is not None
    with attested_connection(database_url):
        pass
    separator = "&" if "?" in database_url else "?"
    overridden_url = database_url + separator + "options=" + quote("-c statement_timeout=0")
    operation = app_factory._BlockedVerification(5)
    token = app_factory._BLOCKED_VERIFICATION.set(operation)
    engine = app_factory._create_startup_evidence_engine(overridden_url)
    try:
        with pytest.raises(SchemaCompatibilityError, match="options are unsupported"):
            engine.connect()
    finally:
        operation.cancel()
        app_factory._BLOCKED_VERIFICATION.reset(token)
        engine.dispose()


def test_postgres_startup_evidence_cancels_active_real_query() -> None:
    """Cancellation interrupts an observed PostgreSQL query before its server deadline."""
    import os
    import time

    from sqlalchemy.exc import DBAPIError

    from tests.integration.postgresql_disposable_cluster import URL_ENV, attested_connection

    database_url = os.environ.get(URL_ENV)
    if not database_url:
        pytest.skip("requires the fresh disposable PostgreSQL harness")
    assert database_url is not None
    operation = app_factory._BlockedVerification(20)
    token = app_factory._BLOCKED_VERIFICATION.set(operation)
    engine = app_factory._create_startup_evidence_engine(database_url)
    backend_pid: list[int] = []
    errors: list[Exception] = []
    connected = threading.Event()

    def run_query() -> None:
        """Run a bounded query on the connection registered with the operation guard."""
        try:
            with engine.connect() as connection:
                backend_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                connected.set()
                connection.exec_driver_sql("SELECT pg_sleep(12)")
        except Exception as exc:  # noqa: BLE001 - preserve the real driver outcome for the assertion
            errors.append(exc)
            connected.set()

    worker = threading.Thread(target=run_query)
    try:
        with attested_connection(database_url) as observer:
            observer.autocommit = True
            worker.start()
            assert connected.wait(8), "PostgreSQL query did not acquire a connection"
            assert backend_pid, f"PostgreSQL connection failed: {[type(error).__name__ for error in errors]}"
            deadline = time.monotonic() + 5
            active = False
            with observer.cursor() as cursor:
                while time.monotonic() < deadline:
                    cursor.execute("SELECT state, query FROM pg_stat_activity WHERE pid = %s", (backend_pid[0],))
                    row = cursor.fetchone()
                    if row and row[0] == "active" and "pg_sleep(12)" in row[1]:
                        active = True
                        break
                    time.sleep(0.05)
            assert active, "PostgreSQL query did not become active"
            cancelled_at = time.monotonic()
            operation.cancel()
            worker.join(8)
            assert not worker.is_alive(), "cancelled PostgreSQL query did not finish"
            assert time.monotonic() - cancelled_at < 8
            assert len(errors) == 1 and isinstance(errors[0], DBAPIError)
    finally:
        operation.cancel()
        if worker.ident is not None:
            worker.join(8)
        app_factory._BLOCKED_VERIFICATION.reset(token)
        engine.dispose()
