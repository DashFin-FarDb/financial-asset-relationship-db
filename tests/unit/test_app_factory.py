"""Unit tests for app factory lifecycle behavior."""

from __future__ import annotations

import pytest  # pylint: disable=import-error
from fastapi import FastAPI

from api import app_factory

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_lifespan_calls_shutdown_rebuild_executor_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan should shut down the rebuild executor when the app stops."""
    app = FastAPI()
    shutdown_calls = []

    def fake_shutdown() -> None:
        """Record shutdown invocation."""
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
        """Avoid real delay in test."""
        return None

    monkeypatch.setattr(app_factory.asyncio, "sleep", immediate_sleep)
    monkeypatch.setattr(
        app_factory,
        "get_runtime_lifecycle_state",
        lambda: app_factory.GraphRuntimeLifecycleState.SHUTTING_DOWN,
    )

    sync_calls: list[bool] = []

    async def fake_to_thread(_fn):
        sync_calls.append(True)
        return None

    monkeypatch.setattr(app_factory.asyncio, "to_thread", fake_to_thread)

    await app_factory._run_graph_sync_loop(interval_seconds=0)  # pylint: disable=protected-access
    assert sync_calls == []
