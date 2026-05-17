"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest  # pylint: disable=import-error
from fastapi import FastAPI

from api import app_factory
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

    if init_calls:
        raise AssertionError("executor should not initialize when startup reconciliation is blocked")
