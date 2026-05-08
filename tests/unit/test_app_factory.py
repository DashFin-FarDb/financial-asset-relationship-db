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
