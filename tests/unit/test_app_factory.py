"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest  # pylint: disable=import-error
from fastapi import FastAPI

from api import app_factory
from src.data.database import init_db as database_init_db
from src.logic.recovery_gate import ExecutionBlockedError

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_lifespan_calls_shutdown_rebuild_executor_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan should shut down the rebuild executor when the app stops."""
    app = FastAPI()
    shutdown_calls = []

    async def fake_shutdown() -> None:
        """Record shutdown invocation (async to match actual signature)."""
        shutdown_calls.append(True)

    def fake_get_graph() -> object:
        """Return a non-None graph placeholder for lifespan startup."""
        return object()

    monkeypatch.setattr(app_factory, "get_graph", fake_get_graph)
    monkeypatch.setattr(app_factory, "shutdown_rebuild_executor", fake_shutdown)

    async with app_factory.lifespan(app):
        assert shutdown_calls == []

    assert shutdown_calls == [True]


@pytest.mark.asyncio
async def test_sync_loop_stops_without_syncing_when_shutting_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background sync loop should exit cleanly once shutdown state is observed."""

    async def immediate_sleep(_seconds: int) -> None:
        """Avoid real delay in test - returns immediately."""
        pass

    monkeypatch.setattr(app_factory.asyncio, "sleep", immediate_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.SHUTTING_DOWN,
    )

    sync_calls: list[bool] = []

    async def fake_to_thread(_fn):
        """Mock asyncio.to_thread - returns immediately."""
        sync_calls.append(True)
        return None

    monkeypatch.setattr(app_factory.asyncio, "to_thread", fake_to_thread)

    await app_factory._run_graph_sync_loop(interval_seconds=0)  # pylint: disable=protected-access
    assert sync_calls == []


@pytest.mark.asyncio
async def test_lifespan_blocks_startup_when_reconciliation_is_execution_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan should propagate recovery-gate execution blocks at startup."""
    app = FastAPI()
    init_calls: list[bool] = []

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: SimpleNamespace(asset_graph_database_url="sqlite:///:memory:"),
    )
    monkeypatch.setattr(app_factory, "get_graph", object)
    monkeypatch.setattr(
        app_factory,
        "init_rebuild_executor",
        lambda: init_calls.append(True),
    )

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(app_factory.asyncio, "to_thread", fake_to_thread)

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
) -> None:
    """Lifespan must fail startup if defensive init_db also fails."""
    app = FastAPI()
    init_calls: list[bool] = []

    monkeypatch.setattr(
        "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
        lambda: SimpleNamespace(asset_graph_database_url="sqlite:///./test-startup.db"),
    )
    monkeypatch.setattr(app_factory, "get_graph", object)
    monkeypatch.setattr(
        app_factory,
        "init_rebuild_executor",
        lambda: init_calls.append(True),
    )

    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
        raise RuntimeError("reconciliation failed")

    monkeypatch.setattr(
        app_factory,
        "_run_startup_reconciliation",
        _raise_reconciliation_failure,
    )

    async def fake_to_thread(fn, *args, **kwargs):
        if fn == database_init_db:
            raise RuntimeError("init_db failed")
        return fn(*args, **kwargs)

    monkeypatch.setattr(app_factory.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(RuntimeError, match="init_db failed"):
        async with app_factory.lifespan(app):
            pass

    assert not init_calls, "executor should not initialize when defensive init_db fails"


def test_startup_reconciliation_does_not_release_lock_without_reset_reacquire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup reconciliation should skip release when RESET did not reacquire."""
    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    class _GateNoReacquire:
        def __init__(self, **_kwargs) -> None:
            self.lock_was_reacquired = False

        def ensure_safe_to_execute(self) -> None:
            raise ExecutionBlockedError("wait", action="wait", inconsistency_type="none")

    monkeypatch.setattr("api.graph_lifecycle_providers.resolve_durable_graph_persistence_url", lambda _url: "sqlite:///x")
    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.init_db", lambda _engine: None)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: object())
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", _GateNoReacquire)

    settings = SimpleNamespace(asset_graph_database_url="sqlite:///x")
    app_factory._run_startup_reconciliation(settings)  # pylint: disable=protected-access

    fake_lock.release.assert_not_called()


def test_startup_reconciliation_releases_lock_when_reset_reacquired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup reconciliation should release lock when RESET reacquired it."""
    fake_engine = SimpleNamespace(dispose=lambda: None)
    fake_lock = SimpleNamespace(lock_name="graph_rebuild", release=MagicMock())

    class _GateReacquired:
        def __init__(self, **_kwargs) -> None:
            self.lock_was_reacquired = True

        def ensure_safe_to_execute(self) -> None:
            return None

    monkeypatch.setattr("api.graph_lifecycle_providers.resolve_durable_graph_persistence_url", lambda _url: "sqlite:///x")
    monkeypatch.setattr("src.data.database.create_engine_from_url", lambda _url: fake_engine)
    monkeypatch.setattr("src.data.database.init_db", lambda _engine: None)
    monkeypatch.setattr("src.data.database.create_session_factory", lambda _engine: object())
    monkeypatch.setattr("src.data.distributed_lock.DistributedLock", lambda **_kwargs: fake_lock)
    monkeypatch.setattr("src.logic.recovery_gate.RecoveryGate", _GateReacquired)

    settings = SimpleNamespace(asset_graph_database_url="sqlite:///x")
    app_factory._run_startup_reconciliation(settings)  # pylint: disable=protected-access

    fake_lock.release.assert_called_once()
