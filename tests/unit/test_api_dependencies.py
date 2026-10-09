"""Unit tests for shared FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import api.graph_lifecycle as graph_lifecycle
from api.graph_lifecycle_providers import AuthoritativeGraphUnavailableError
from src.api.dependencies import get_graph
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_lifecycle() -> Iterator[None]:
    """Reset graph lifecycle state around each test."""
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()


def test_get_graph_returns_lifecycle_graph() -> None:
    """get_graph should return the authoritative active lifecycle graph."""
    custom_graph = AssetRelationshipGraph()
    graph_lifecycle.set_graph(custom_graph)

    active = get_graph()
    assert active is custom_graph


def test_get_graph_fails_closed_when_uninitialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_graph must fail closed and raise AuthoritativeGraphUnavailableError if not initialized."""
    from src.config.settings import get_settings

    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)
    monkeypatch.delenv("REAL_DATA_CACHE_PATH", raising=False)
    monkeypatch.delenv("USE_REAL_DATA_FETCHER", raising=False)

    get_settings.cache_clear()
    try:
        with pytest.raises(AuthoritativeGraphUnavailableError, match="No authoritative published graph available."):
            get_graph()
    finally:
        get_settings.cache_clear()
