"""Unit tests for persisted graph startup loading."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

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
    """
    Constructs a RegulatoryEvent with sensible default fields used by persistence tests.

    Parameters:
        event_id (str): Unique identifier for the event.
        asset_id (str): ID of the asset the event is associated with.
        related_assets (list[str] | None): Optional list of related asset IDs; defaults to an empty list when None.

    Returns:
        RegulatoryEvent: A RegulatoryEvent populated with the provided IDs, a fixed SEC filing type and date, a short description, and an impact score.
    """
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
    """
    Retrieve the stored strength of the relationship from source_id to target_id for the given relationship_type.

    Returns:
        float: The relationship strength.

    Raises:
        AssertionError: If no matching relationship exists in the graph.
    """
    for target, rel_type, strength in graph.relationships.get(source_id, []):
        if target == target_id and rel_type == relationship_type:
            return strength
    raise AssertionError(f"Missing relationship {source_id}->{target_id} ({relationship_type})")


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """
    Build a file-backed SQLite connection URL located under the given directory.

    Parameters:
        tmp_path (Path): Directory in which to place the SQLite database file.
        name (str): Filename for the SQLite database (defaults to "asset_graph.db").

    Returns:
        sqlite_url (str): A SQLite connection URL pointing to the file at tmp_path / name.
    """
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """
    Initialize the database schema at the given database URL.

    Parameters:
        database_url (str): SQLAlchemy connection URL for the target database; the function will create the necessary tables/schema at this location.
    """
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """
    Persist a graph snapshot into the database at the given SQLAlchemy URL.

    Parameters:
        database_url (str): SQLAlchemy connection URL for the target database.
        graph (AssetRelationshipGraph): AssetRelationshipGraph instance to persist.
    """
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
    """
    Builds an AssetRelationshipGraph containing a single equity asset and no relationships or events.

    Returns:
        AssetRelationshipGraph: Graph containing one asset with id "ASSET_ONLY" and symbol "ONLY".
    """
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("ASSET_ONLY", "ONLY"))
    return graph


def _full_graph() -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph containing three equities, two directed relationships, and one regulatory event.

    Returns:
        graph (AssetRelationshipGraph): Graph with assets "ASSET_A", "ASSET_B", and "ASSET_C"; relationships "ASSET_A" -> "ASSET_B" with `directed_alpha` 0.4 and "ASSET_B" -> "ASSET_A" with `directed_alpha` 0.9; and a regulatory event "EVENT_A" attached to "ASSET_A" referencing "ASSET_B" and "ASSET_C".
    """
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
        """
        Always raise an AssertionError to signal that engine creation must not be attempted.

        Raises:
            AssertionError: Always raised with the message "persistence load should not be attempted".
        """
        raise AssertionError("persistence load should not be attempted")

    factory_graph = AssetRelationshipGraph()
    graph_lifecycle.set_graph_factory(lambda: factory_graph)
    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_create_engine(_url: str) -> Any:
        """
        Always raise an AssertionError to signal that engine creation must not be attempted.

        Raises:
            AssertionError: Always raised with the message "persistence load should not be attempted".
        """
        raise AssertionError("persistence load should not be attempted")

    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

    graph = graph_lifecycle._initialize_graph()

    assert graph.assets


@pytest.mark.parametrize(
    "in_memory_url",
    [
        "sqlite:///:memory:",
        "sqlite:///:memory:?check_same_thread=false",
        "sqlite:///file:testmem?mode=memory",
    ],
)
def test_in_memory_sqlite_url_skips_persistence_load(
    in_memory_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory SQLite URLs must be skipped rather than creating a fresh empty engine."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", in_memory_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_create_engine(_url: str) -> Any:
        raise AssertionError("engine creation must not be attempted for in-memory URL")

    monkeypatch.setattr(graph_lifecycle_providers, "create_engine_from_url", fail_create_engine)

    graph = graph_lifecycle._initialize_graph()

    assert graph.assets  # falls back to sample data


@pytest.mark.parametrize(
    ("env_name", "env_value", "provider_attr"),
    [
        ("GRAPH_CACHE_PATH", "/tmp/graph-cache.json", "load_graph_from_cache_path"),
        ("USE_REAL_DATA_FETCHER", "1", "load_graph_from_real_data_fetcher"),
    ],
)
def test_empty_configured_db_honors_configured_source_before_sample_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    env_value: str,
    provider_attr: str,
) -> None:
    """An empty configured persistence store must still honor higher-precedence configured sources."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    monkeypatch.setenv(env_name, env_value)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """
        Raise an AssertionError to fail the test if an attempt is made to save the graph during startup.

        This helper always raises AssertionError("startup load must not save graph data") to indicate that saving persisted graph data during initialization is unexpected.
        """
        raise AssertionError("startup load must not save graph data")

    configured_graph = _asset_only_graph()

    def load_configured_graph(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        return configured_graph

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)
    monkeypatch.setattr(
        graph_lifecycle_providers,
        provider_attr,
        load_configured_graph,
    )

    graph = graph_lifecycle._initialize_graph()

    assert graph is configured_graph
    assert set(graph.assets) == {"ASSET_ONLY"}


def test_persisted_asset_only_graph_loads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One persisted asset is enough to select repository startup loading."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        graph_lifecycle._initialize_graph()


def test_invalid_configured_database_url_fails_without_leaking_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid configured persistence should fail with sanitized lifecycle text."""
    raw_url = "not-a-sqlalchemy-url://user:secret@example.invalid/db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", raw_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    with pytest.raises(RuntimeError) as exc_info:
        graph_lifecycle._initialize_graph()

    assert exc_info.value.__context__ is None
    message = str(exc_info.value)
    assert "Failed to load persisted graph during startup" in message
    assert "secret" not in message
    assert raw_url not in message


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

    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        graph_lifecycle._initialize_graph()


def test_session_closes_on_success_empty_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close its short-lived session in every path."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _asset_only_graph())
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    close_calls = 0
    real_create_session_factory = graph_lifecycle_providers.create_session_factory

    def tracking_session_factory(engine: Any) -> Any:
        """
        Create a session factory whose sessions are wrapped with ClosingSessionProxy.

        Parameters:
            engine: The database engine used to build the underlying session factory.

        Returns:
            A callable that, when invoked, returns a session proxy delegating to a real session created from `engine`, with `close()` proxied for tracking.
        """
        real_factory = real_create_session_factory(engine)

        def make_session() -> Any:
            """
            Create a new database session wrapped by a ClosingSessionProxy.

            Returns:
                ClosingSessionProxy: A proxy around the newly created session that delegates session operations to the real session and exposes a close() implementation suitable for tracking/overriding close calls.
            """
            session = real_factory()
            return ClosingSessionProxy(session)

        return make_session

    class ClosingSessionProxy:
        """Proxy a SQLAlchemy session and count close calls."""

        def __init__(self, session: Any) -> None:
            """
            Initialize the repository with a database session.

            Parameters:
                session (Any): A database session instance used for persistence operations (short-lived SQLAlchemy
                    session or equivalent). The repository retains this session for its lifetime.
            """
            self._session = session

        def __getattr__(self, name: str) -> Any:
            """
            Delegate attribute access to the proxied session.

            Forward attribute lookups to self._session so that attributes and methods on the underlying session
            are accessible through this proxy.

            Parameters:
                name (str): Name of the attribute being accessed.

            Returns:
                Any: The attribute value from the underlying session.
            """
            return getattr(self._session, name)

        def close(self) -> None:
            """
            Increment the external close counter and close the proxied session.

            Increments the nonlocal `close_calls` counter used by tests and delegates to the wrapped session's `close()` method.
            """
            nonlocal close_calls
            close_calls += 1
            self._session.close()

    monkeypatch.setattr(graph_lifecycle_providers, "create_session_factory", tracking_session_factory)
    graph_lifecycle._initialize_graph()
    assert close_calls == 1

    empty_url = _sqlite_url(tmp_path, "empty.db")
    _init_empty_db(empty_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", empty_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    graph_lifecycle._initialize_graph()
    assert close_calls == 2

    missing_schema_url = _sqlite_url(tmp_path, "missing.db")
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", missing_schema_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """
        Fail the test if a graph save is attempted during reset or startup load.

        This helper unconditionally raises an AssertionError to ensure code paths invoked
        during reset/startup do not attempt to persist graph data.

        Raises:
            AssertionError: with message "reset/startup load must not save graph data".
        """
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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
