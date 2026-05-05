"""Unit tests for persisted graph startup loading."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

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
    """
    Reset the graph lifecycle and clear persistence-related environment variables before each test, then reset the lifecycle again after the test.
    
    This fixture removes the environment variables ASSET_GRAPH_DATABASE_URL, GRAPH_CACHE_PATH, REAL_DATA_CACHE_PATH, and USE_REAL_DATA_FETCHER to ensure tests start with a clean persisted-graph configuration and to prevent leakage between tests.
    """
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
    """
    Retrieve the stored strength value for the specified relationship.
    
    @returns
        The relationship strength as a float.
    
    @raises AssertionError
        If no relationship matching `source_id`, `target_id`, and `relationship_type` is found.
    """
    for target, rel_type, strength in graph.relationships.get(source_id, []):
        if target == target_id and rel_type == relationship_type:
            return strength
    raise AssertionError(f"Missing relationship {source_id}->{target_id} ({relationship_type})")


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """
    Construct a file-backed SQLite URL pointing to a database file under the given directory.
    
    Parameters:
        tmp_path (Path): Directory in which the SQLite file will be placed.
        name (str): Filename for the SQLite database (defaults to "asset_graph.db").
    
    Returns:
        str: A SQLite URL string referencing the file (e.g., "sqlite:///path/to/{name}").
    """
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """Create the graph database schema without graph rows."""
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """
    Persist the given AssetRelationshipGraph into the database identified by `database_url`.
    
    Parameters:
        database_url (str): SQLAlchemy database URL for the test database (file-backed or in-memory).
        graph (AssetRelationshipGraph): In-memory graph snapshot to be saved.
    
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
    Create an in-memory asset relationship graph containing a single equity and no relationships or events.
    
    Returns:
        AssetRelationshipGraph: Graph with one asset (id "ASSET_ONLY", symbol "ONLY") and no relationships or regulatory events.
    """
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity("ASSET_ONLY", "ONLY"))
    return graph


def _full_graph() -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph containing three equities, two directed relationships, and one regulatory event.
    
    Returns:
        AssetRelationshipGraph: Graph with assets "ASSET_A", "ASSET_B", and "ASSET_C"; relationships
        "ASSET_A" -> "ASSET_B" with type "directed_alpha" and strength 0.4, and
        "ASSET_B" -> "ASSET_A" with type "directed_alpha" and strength 0.9; and a regulatory
        event "EVENT_A" attached to "ASSET_A" with related assets ["ASSET_B", "ASSET_C"].
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


def _initialize_graph_for_test() -> AssetRelationshipGraph:
    """
    Initialize the asset relationship graph via the lifecycle test seam.
    
    Returns:
        AssetRelationshipGraph: The initialized graph instance used by tests.
    """
    return graph_lifecycle._initialize_graph()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Session-close tracking proxy and patch helper
# ---------------------------------------------------------------------------


class _ClosingSessionProxy:
    """Proxy a SQLAlchemy session and count close calls."""

    def __init__(self, session: Any, close_counter: Callable[[], None]) -> None:
        """
        Initialize the proxy with a wrapped session and a callback to record close calls.
        
        Parameters:
            session: The underlying SQLAlchemy session to proxy.
            close_counter: A zero-argument callable invoked each time the proxy's `close()` is called to increment the external close-call counter.
        """
        self._session = session
        self._close_counter = close_counter

    def __getattr__(self, name: str) -> Any:
        """
        Delegate attribute access to the wrapped SQLAlchemy session.
        
        Parameters:
            name (str): The attribute name to retrieve from the wrapped session.
        
        Returns:
            Any: The attribute value from the underlying session.
        
        Raises:
            AttributeError: If the underlying session does not have the requested attribute.
        """
        return getattr(self._session, name)

    def close(self) -> None:
        """
        Increment the tracked close counter and close the wrapped SQLAlchemy session.
        
        Increments the provided close-call counter and then delegates to the underlying
        session's `close()` method to release database resources.
        """
        self._close_counter()
        self._session.close()


def _patch_session_close_counter(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    """
    Patch the session factory so created sessions are wrapped and their `.close()` calls are counted.
    
    This replaces graph_lifecycle_providers.create_session_factory via the provided pytest monkeypatch so sessions returned by the factory are proxied to increment an internal counter each time `close()` is invoked.
    
    Parameters:
        monkeypatch (pytest.MonkeyPatch): Fixture used to set the patched session factory.
    
    Returns:
        Callable[[], int]: A zero-argument callable that returns the current count of `close()` calls.
    """
    close_calls = 0
    real_create_session_factory = graph_lifecycle_providers.create_session_factory

    def increment_close_calls() -> None:
        """
        Increment the internal counter tracking how many times proxied sessions were closed.
        
        Used by the session proxy to record each `.close()` invocation.
        """
        nonlocal close_calls
        close_calls += 1

    def tracking_session_factory(engine: Any) -> Any:
        """
        Create a session factory that produces sessions wrapped with a proxy which increments a close-call counter when closed.
        
        The returned callable takes no arguments and produces a `_ClosingSessionProxy` that delegates to a real SQLAlchemy session while incrementing the provided close-count on each `.close()` call.
        
        Parameters:
            engine: The SQLAlchemy engine passed through to the underlying session factory.
        
        Returns:
            session_factory (Callable[[], Any]): A zero-argument callable that returns a proxied session whose `close()` increments the tracked close-call counter and then closes the underlying session.
        """
        real_factory = real_create_session_factory(engine)

        def make_session() -> Any:
            """
            Return a session proxy that increments a close-call counter each time its .close() is invoked.
            
            This wraps a real SQLAlchemy session produced by the factory and delegates all attributes
            and method calls to it while counting calls to .close().
            
            Returns:
                _ClosingSessionProxy: Proxy around the real session that increments the configured counter on `.close()` and forwards all other behavior to the underlying session.
            """
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
    """
    Verify that when a persisted database exists but contains no graph rows, startup falls through to a configured non-persistent graph provider and does not attempt to save to the database.
    
    This test helper:
    - Creates an empty file-backed SQLite database and sets ASSET_GRAPH_DATABASE_URL to it.
    - Monkeypatches the specified provider (given by `provider_attr`) to return a configured in-memory graph and replaces AssetGraphRepository.save_graph with a function that fails if called.
    - Calls the lifecycle initializer and asserts the returned graph is the configured graph and contains only the expected asset ("ASSET_ONLY").
    """
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """
        Raise an AssertionError to indicate startup attempted to save graph data.
        
        Raises:
            AssertionError: Always raised with message "startup load must not save graph data".
        """
        raise AssertionError("startup load must not save graph data")

    configured_graph = _asset_only_graph()

    def load_configured_graph(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """
        Provide the preconfigured fallback AssetRelationshipGraph instance.
        
        Returns:
            AssetRelationshipGraph: The configured fallback graph object.
        """
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
        """
        Fail when called to indicate persistence engine creation must not occur when a graph factory is configured.
        
        Raises:
            AssertionError: always raised with message "persistence load should not be attempted".
        """
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
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", configured_value)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    loaded = _initialize_graph_for_test()

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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    with pytest.raises(RuntimeError, match="Failed to load persisted graph during startup"):
        _initialize_graph_for_test()


def test_invalid_configured_database_url_fails_without_leaking_url(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Ensure startup fails when ASSET_GRAPH_DATABASE_URL is invalid and that the resulting error message and logs do not expose the raw URL or embedded secrets.
    
    Verifies that initializing the graph raises a RuntimeError with the text "Failed to load persisted graph during startup" and that neither the full configured URL nor secret substrings appear in the exception message or captured log output.
    """
    raw_url = "not-a-real-driver://user:secret@example.invalid/db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", raw_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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

    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    close_count = _patch_session_close_counter(monkeypatch)

    _initialize_graph_for_test()

    assert close_count() == 1


def test_session_closes_on_persistence_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup load should close the session after load failure."""
    database_url = _sqlite_url(tmp_path)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
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
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """
        Raise an AssertionError to fail tests when a reset or startup load attempts to persist the graph.
        
        Used as a test stub replacement for persistence calls to ensure startup/reset code does not write to storage.
        
        Raises:
            AssertionError: always; indicates the code under test attempted to save graph data when it must not.
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
