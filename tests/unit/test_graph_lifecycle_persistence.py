"""Unit tests for persisted graph startup loading."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable  # noqa: UP035  # Callable from typing for Prospector/Pylint compatibility

import pytest
from sqlalchemy import create_engine, text  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as graph_lifecycle_providers
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
    """Reset graph lifecycle and clear persistence env vars."""
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


# ---------------------------------------------------------------------------
# Module-level helpers and data builders
# ---------------------------------------------------------------------------


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
    """Build a regulatory event for persistence tests."""
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
    """Retrieve the stored strength value for the specified relationship."""
    for target, rel_type, strength in graph.relationships.get(source_id, []):
        if target == target_id and rel_type == relationship_type:
            return strength
    raise AssertionError(f"Missing relationship {source_id}->{target_id} ({relationship_type})")


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """Construct a file-backed SQLite URL."""
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """Create the graph database schema without graph rows."""
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """Persist the given graph into the database."""
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
    """Create a graph with one asset and no relationships or events."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("ASSET_ONLY", "ONLY"))
    return graph


def _full_graph() -> AssetRelationshipGraph:
    """Create a graph with assets, relationships, and a regulatory event."""
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


def _initialize_graph_for_test() -> AssetRelationshipGraph:
    """Initialize the graph via the lifecycle test seam."""
    return graph_lifecycle._initialize_graph()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Session-close tracking proxy and patch helper
# ---------------------------------------------------------------------------


def _configure_persistence_url(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
) -> None:
    """Set graph persistence URL and clear cached lifecycle settings."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()


class _ClosingSessionProxy:
    """Proxy a SQLAlchemy session and count close calls."""

    def __init__(self, session: Any, close_counter: Callable[[], None]) -> None:
        """Initialize the proxy with a session and close-call callback."""
        self._session = session
        self._close_counter = close_counter

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped session."""
        return getattr(self._session, name)

    def close(self) -> None:
        """Increment the close counter and close the session."""
        self._close_counter()
        self._session.close()


def _patch_session_close_counter(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    """Patch session factory to count close calls."""
    close_calls = 0
    real_create_session_factory = graph_lifecycle_providers.create_session_factory

    def increment_close_calls() -> None:
        """Increment the close-call counter."""
        nonlocal close_calls
        close_calls += 1

    def tracking_session_factory(engine: Any) -> Any:
        """Create a session factory that produces close-counting sessions."""
        real_factory = real_create_session_factory(engine)

        def make_session() -> Any:
            """Return a session proxy that counts close calls."""
            return _ClosingSessionProxy(real_factory(), increment_close_calls)

        return make_session

    monkeypatch.setattr(
        graph_lifecycle_providers,
        "create_session_factory",
        tracking_session_factory,
    )
    return lambda: close_calls


# ---------------------------------------------------------------------------
# Empty-persistence fallback helper
# ---------------------------------------------------------------------------


def _assert_empty_db_uses_configured_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_attr: str,
) -> None:
    """Verify empty DB falls through to configured provider."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence_url(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if startup attempts to save graph data."""
        raise AssertionError("startup load must not save graph data")

    configured_graph = _asset_only_graph()

    def load_configured_graph(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Provide the preconfigured fallback graph."""
        return configured_graph

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)
    monkeypatch.setattr(
        graph_lifecycle_providers,
        provider_attr,
        load_configured_graph,
    )

    graph = _initialize_graph_for_test()

    assert graph is configured_graph
    assert set(graph.assets) == {"ASSET_ONLY"}


# ---------------------------------------------------------------------------
# Tests: factory and persistence-disabled precedence
# ---------------------------------------------------------------------------


def test_factory_precedence_skips_persistence_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured factories should win before any repository load attempt."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)

    def fail_create_engine(_url: str) -> Any:
        """Fail to indicate persistence must not be attempted."""
        raise AssertionError("persistence load should not be attempted")

    factory_graph = AssetRelationshipGraph()
    graph_lifecycle.set_graph_factory(lambda: factory_graph)
    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

    assert _initialize_graph_for_test() is factory_graph


@pytest.mark.parametrize("configured_value", [None, "", "   "])
def test_persistence_disabled_preserves_sample_fallback(
    configured_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset or blank graph persistence should preserve existing fallback behavior."""
    if configured_value is None:
        monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    else:
        _configure_persistence_url(monkeypatch, configured_value)

    def fail_create_engine(_url: str) -> Any:
        """Fail if engine creation is attempted for a disabled persistence URL."""
        raise AssertionError("persistence load should not be attempted")

    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

    graph = _initialize_graph_for_test()

    assert graph.assets


@pytest.mark.parametrize(
    "in_memory_url",
    [
        "sqlite:///:memory:",
        "sqlite:///:memory:?check_same_thread=false",
        "sqlite:///file:testmem?mode=memory",
        "sqlite://",
        "sqlite+pysqlite://",
        "sqlite:///file::memory:?cache=shared",
        "sqlite+pysqlite:///file::memory:?cache=shared",
    ],
)
def test_in_memory_sqlite_url_skips_persistence_load(
    in_memory_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory SQLite URLs must be skipped."""
    _configure_persistence_url(monkeypatch, in_memory_url)

    def fail_create_engine(_url: str) -> Any:
        """Fail if in-memory SQLite attempts engine creation."""
        raise AssertionError("engine creation must not be attempted for in-memory URL")

    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

    graph = _initialize_graph_for_test()

    assert graph.assets  # falls back to sample data


# ---------------------------------------------------------------------------
# Tests: empty-store fallback honors configured sources
# ---------------------------------------------------------------------------


def test_empty_configured_db_honors_graph_cache_path_before_sample_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty persistence should fall through to GRAPH_CACHE_PATH."""
    monkeypatch.setenv("GRAPH_CACHE_PATH", "/tmp/graph-cache.json")
    _assert_empty_db_uses_configured_source(
        tmp_path,
        monkeypatch,
        "load_graph_from_cache_path",
    )


def test_empty_configured_db_honors_real_data_fetcher_before_sample_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty persistence should fall through to USE_REAL_DATA_FETCHER."""
    monkeypatch.setenv("USE_REAL_DATA_FETCHER", "1")
    _assert_empty_db_uses_configured_source(
        tmp_path,
        monkeypatch,
        "load_graph_from_real_data_fetcher",
    )


# ---------------------------------------------------------------------------
# Tests: successful persisted loads
# ---------------------------------------------------------------------------


def test_persisted_asset_only_graph_loads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One persisted asset is enough to select repository startup loading."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    _configure_persistence_url(monkeypatch, database_url)

    loaded = _initialize_graph_for_test()

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
    _configure_persistence_url(monkeypatch, database_url)

    loaded = _initialize_graph_for_test()

    assert set(loaded.assets) == {"ASSET_A", "ASSET_B", "ASSET_C"}
    assert _relationship_strength(loaded, "ASSET_A", "ASSET_B", "directed_alpha") == pytest.approx(0.4)
    assert _relationship_strength(loaded, "ASSET_B", "ASSET_A", "directed_alpha") == pytest.approx(0.9)
    assert [event.id for event in loaded.regulatory_events] == ["EVENT_A"]


def test_populated_persistence_wins_over_graph_cache_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Populated persistence should win over GRAPH_CACHE_PATH."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    _configure_persistence_url(monkeypatch, database_url)
    monkeypatch.setenv("GRAPH_CACHE_PATH", "/tmp/graph-cache.json")

    def fail_cache_load(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Fail if cache fallback is used before persistence."""
        raise AssertionError("cache fallback must not run when persistence is populated")

    monkeypatch.setattr(
        graph_lifecycle_providers,
        "load_graph_from_cache_path",
        fail_cache_load,
    )

    loaded = _initialize_graph_for_test()

    assert set(loaded.assets) == {"ASSET_ONLY"}


def test_populated_persistence_wins_over_real_data_fetcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Populated persistence should win over USE_REAL_DATA_FETCHER."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    _configure_persistence_url(monkeypatch, database_url)
    monkeypatch.setenv("USE_REAL_DATA_FETCHER", "1")

    def fail_real_data_load(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Fail if real-data fallback is used before persistence."""
        raise AssertionError("real-data fallback must not run when persistence is populated")

    monkeypatch.setattr(
        graph_lifecycle_providers,
        "load_graph_from_real_data_fetcher",
        fail_real_data_load,
    )

    loaded = _initialize_graph_for_test()

    assert set(loaded.assets) == {"ASSET_ONLY"}


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

    _configure_persistence_url(monkeypatch, database_url)

    loaded = _initialize_graph_for_test()

    assert _relationship_strength(loaded, "LEGACY_A", "LEGACY_B", "same_sector") == pytest.approx(0.7)
    assert _relationship_strength(loaded, "LEGACY_B", "LEGACY_A", "same_sector") == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Tests: failure paths
# ---------------------------------------------------------------------------


def test_missing_schema_fails_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured persistence with missing tables should fail startup load."""
    database_url = _sqlite_url(tmp_path)
    _configure_persistence_url(monkeypatch, database_url)

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        _initialize_graph_for_test()


def test_invalid_configured_database_url_fails_without_leaking_url(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure startup fails on invalid URL without leaking secrets."""
    raw_url = "not-a-real-driver://user:secret@example.invalid/db"
    _configure_persistence_url(monkeypatch, raw_url)

    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as exc_info:
        _initialize_graph_for_test()

    assert exc_info.value.__suppress_context__ is True
    message = str(exc_info.value)
    assert "Failed to load persisted graph during startup" in message
    assert "secret" not in message
    assert raw_url not in message
    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert "secret" not in log_output
    assert raw_url not in log_output


def test_malformed_asset_class_persisted_row_fails_without_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured persistence with a corrupt enum value should fail startup load."""
    database_url = _sqlite_url(tmp_path)
    engine = create_engine(database_url)
    init_db(engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO assets (id, symbol, name, asset_class, sector, price, currency)"
                " VALUES ('BAD_ASSET', 'BAD', 'Bad Asset', 'NOT_A_VALID_CLASS', 'Tech', 1.0, 'USD')"
            )
        )
        conn.commit()
    engine.dispose()

    _configure_persistence_url(monkeypatch, database_url)

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        _initialize_graph_for_test()


# ---------------------------------------------------------------------------
# Tests: session cleanup
# ---------------------------------------------------------------------------


def test_session_closes_on_persisted_load_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close the session after persisted load."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    _configure_persistence_url(monkeypatch, database_url)
    close_count = _patch_session_close_counter(monkeypatch)

    _initialize_graph_for_test()

    assert close_count() == 1


def test_session_closes_on_empty_persistence_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close the session before empty-store fallback."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence_url(monkeypatch, database_url)
    close_count = _patch_session_close_counter(monkeypatch)

    _initialize_graph_for_test()

    assert close_count() == 1


def test_session_closes_on_persistence_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close the session after load failure."""
    database_url = _sqlite_url(tmp_path)
    _configure_persistence_url(monkeypatch, database_url)
    close_count = _patch_session_close_counter(monkeypatch)

    with pytest.raises(RuntimeError):
        _initialize_graph_for_test()

    assert close_count() == 1


# ---------------------------------------------------------------------------
# Tests: reset and compatibility
# ---------------------------------------------------------------------------


def test_reset_reloads_persisted_graph_without_saving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reset_graph should clear cached state and reload without mutating storage."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    _configure_persistence_url(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if reset/startup attempts to save graph data."""
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
    _configure_persistence_url(monkeypatch, database_url)

    import api.main as api_main  # pylint: disable=import-outside-toplevel
    import api.router_helpers as router_helpers  # pylint: disable=import-outside-toplevel

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
