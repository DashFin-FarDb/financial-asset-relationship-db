"""Unit tests for persisted graph startup loading."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

import api.graph_lifecycle as graph_lifecycle
from src.config.settings import get_settings
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_lifecycle(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset graph lifecycle state and graph-source environment for each test."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
    ):
        monkeypatch.delenv(name, raising=False)
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()


def _equity(asset_id: str, symbol: str) -> Equity:
    """Build a minimal equity asset for lifecycle persistence tests."""
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _event(event_id: str, asset_id: str, related_assets: list[str] | None = None) -> RegulatoryEvent:
    """Build a regulatory event for lifecycle persistence tests."""
    return RegulatoryEvent(
        id=event_id,
        asset_id=asset_id,
        event_type=RegulatoryActivity.SEC_FILING,
        date="2024-01-15",
        description=f"{event_id} filing",
        impact_score=0.5,
        related_assets=related_assets or [],
    )


def _relationship_strength(
    graph: AssetRelationshipGraph,
    source_id: str,
    target_id: str,
    relationship_type: str,
) -> float:
    """Return the strength for one graph relationship."""
    for target, rel_type, strength in graph.relationships.get(source_id, []):
        if target == target_id and rel_type == relationship_type:
            return strength
    raise AssertionError(f"Missing relationship {source_id}->{target_id} ({relationship_type})")


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """Return a temporary file-backed SQLite URL."""
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """Create an empty schema-ready graph database."""
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """Persist a graph snapshot to a temporary graph database."""
    engine = create_engine(database_url)
    init_db(engine)
    session = create_session_factory(engine)()
    try:
        AssetGraphRepository(session).save_graph(graph)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _asset_only_graph() -> AssetRelationshipGraph:
    """Build a graph with one persisted asset and no relationships or events."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("ASSET_ONLY", "ONLY"))
    return graph


def _full_graph() -> AssetRelationshipGraph:
    """Build a graph with assets, directed relationships, and an event."""
    graph = AssetRelationshipGraph()
    for asset in (
        _equity("ASSET_A", "A"),
        _equity("ASSET_B", "B"),
        _equity("ASSET_C", "C"),
    ):
        graph.add_asset(asset)
    graph.add_relationship("ASSET_A", "ASSET_B", "directed_alpha", 0.4)
    graph.add_relationship("ASSET_B", "ASSET_A", "directed_alpha", 0.9)
    graph.add_regulatory_event(_event("EVENT_A", "ASSET_A", ["ASSET_B", "ASSET_C"]))
    return graph


def test_factory_precedence_skips_persistence_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured factories should win before any repository load attempt."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)

    def fail_create_engine(_url: str) -> Any:
        raise AssertionError("persistence load should not be attempted")

    factory_graph = AssetRelationshipGraph()
    graph_lifecycle.set_graph_factory(lambda: factory_graph)
    monkeypatch.setattr(graph_lifecycle, "create_engine_from_url", fail_create_engine)

    assert graph_lifecycle._initialize_graph() is factory_graph


@pytest.mark.parametrize("configured_value", [None, "", "   "])
def test_persistence_disabled_preserves_sample_fallback(
    configured_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset or blank graph persistence should preserve existing fallback behavior."""
    if configured_value is None:
        monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", configured_value)
    get_settings.cache_clear()

    def fail_create_engine(_url: str) -> Any:
        raise AssertionError("persistence load should not be attempted")

    monkeypatch.setattr(graph_lifecycle, "create_engine_from_url", fail_create_engine)

    graph = graph_lifecycle._initialize_graph()

    assert graph.assets


def test_empty_configured_db_falls_back_without_saving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A schema-ready empty graph store should fall through to current fallback."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("startup load must not save graph data")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)

    graph = graph_lifecycle._initialize_graph()

    assert graph.assets
    assert "ASSET_ONLY" not in graph.assets


def test_persisted_asset_only_graph_loads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One persisted asset is enough to select repository startup loading."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    loaded = graph_lifecycle._initialize_graph()

    assert set(loaded.assets) == {"ASSET_ONLY"}
    assert not loaded.relationships
    assert not loaded.regulatory_events


def test_persisted_full_graph_loads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup loading should reconstruct persisted graph truth."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _full_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    loaded = graph_lifecycle._initialize_graph()

    assert set(loaded.assets) == {"ASSET_A", "ASSET_B", "ASSET_C"}
    assert _relationship_strength(loaded, "ASSET_A", "ASSET_B", "directed_alpha") == pytest.approx(0.4)
    assert _relationship_strength(loaded, "ASSET_B", "ASSET_A", "directed_alpha") == pytest.approx(0.9)
    assert [event.id for event in loaded.regulatory_events] == ["EVENT_A"]


def test_legacy_bidirectional_row_survives_startup_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy bidirectional rows should keep repository load compatibility."""
    database_url = _sqlite_url(tmp_path)
    engine = create_engine(database_url)
    init_db(engine)
    session = create_session_factory(engine)()
    try:
        repository = AssetGraphRepository(session)
        repository.upsert_asset(_equity("LEGACY_A", "LA"))
        repository.upsert_asset(_equity("LEGACY_B", "LB"))
        repository.add_or_update_relationship(
            "LEGACY_A",
            "LEGACY_B",
            "same_sector",
            0.7,
            bidirectional=True,
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()

    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    loaded = graph_lifecycle._initialize_graph()

    assert _relationship_strength(loaded, "LEGACY_A", "LEGACY_B", "same_sector") == pytest.approx(0.7)
    assert _relationship_strength(loaded, "LEGACY_B", "LEGACY_A", "same_sector") == pytest.approx(0.7)


def test_missing_schema_fails_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured persistence with missing tables should fail startup load."""
    database_url = _sqlite_url(tmp_path)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        graph_lifecycle._initialize_graph()


def test_invalid_configured_database_url_fails_without_leaking_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid configured persistence should fail with sanitized lifecycle text."""
    raw_url = "not-a-sqlalchemy-url://user:secret@example.invalid/db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", raw_url)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as exc_info:
        graph_lifecycle._initialize_graph()

    message = str(exc_info.value)
    assert "Failed to load persisted graph during startup" in message
    assert "secret" not in message
    assert raw_url not in message


def test_session_closes_on_success_empty_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close its short-lived session in every path."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()
    close_calls = 0
    real_create_session_factory = graph_lifecycle.create_session_factory

    def tracking_session_factory(engine: Any) -> Any:
        real_factory = real_create_session_factory(engine)

        def make_session() -> Any:
            session = real_factory()
            return ClosingSessionProxy(session)

        return make_session

    class ClosingSessionProxy:
        """Proxy a SQLAlchemy session and count close calls."""

        def __init__(self, session: Any) -> None:
            self._session = session

        def __getattr__(self, name: str) -> Any:
            return getattr(self._session, name)

        def close(self) -> None:
            nonlocal close_calls
            close_calls += 1
            self._session.close()

    monkeypatch.setattr(graph_lifecycle, "create_session_factory", tracking_session_factory)
    graph_lifecycle._initialize_graph()
    assert close_calls == 1

    empty_url = _sqlite_url(tmp_path, "empty.db")
    _init_empty_db(empty_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", empty_url)
    get_settings.cache_clear()
    graph_lifecycle._initialize_graph()
    assert close_calls == 2

    missing_schema_url = _sqlite_url(tmp_path, "missing.db")
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", missing_schema_url)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        graph_lifecycle._initialize_graph()
    assert close_calls == 3


def test_reset_reloads_persisted_graph_without_saving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reset_graph should clear cached state and reload without mutating storage."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("reset/startup load must not save graph data")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)

    first = graph_lifecycle.get_graph()
    graph_lifecycle.reset_graph()
    second = graph_lifecycle.get_graph()

    assert first is not second
    assert set(second.assets) == {"ASSET_ONLY"}


def test_api_main_and_router_helper_compatibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatibility graph references should converge around lifecycle loading."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()

    import api.main as api_main
    import api.router_helpers as router_helpers

    api_main = importlib.reload(api_main)
    try:
        loaded = api_main.get_graph()

        assert set(loaded.assets) == {"ASSET_ONLY"}
        assert graph_lifecycle.get_graph() is loaded
        assert router_helpers.get_graph() is api_main.graph

        api_main.reset_graph()
        assert api_main.graph is None
        reloaded = router_helpers.get_graph()
        assert set(reloaded.assets) == {"ASSET_ONLY"}

        custom_graph = AssetRelationshipGraph()
        api_main.set_graph(custom_graph)
        assert router_helpers.get_graph() is custom_graph
    finally:
        api_main.reset_graph()
