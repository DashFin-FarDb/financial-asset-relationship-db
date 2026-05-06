"""Tests for explicit graph rebuild persistence."""

from __future__ import annotations

import logging
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Iterator, Tuple

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from sqlalchemy import create_engine  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
import api.main as api_main
from api.api_models import DatabaseHealthResponse
from api.app_factory import create_app
from api.auth import User, get_current_active_user
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Reset graph-related environment, caches, and runtime graph before a test and restore them after.

    This fixture clears environment variables used for graph persistence and caching (ASSET_GRAPH_DATABASE_URL, GRAPH_CACHE_PATH, REAL_DATA_CACHE_PATH, USE_REAL_DATA_FETCHER), clears the graph lifecycle settings cache, resets the in-memory runtime graph, and replaces the rebuild executor with an immediate executor so rebuild tasks run synchronously. After the test yields, the fixture resets the runtime graph and clears the lifecycle settings cache again.
    """
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
    ):
        monkeypatch.delenv(name, raising=False)
    providers.clear_graph_lifecycle_settings_cache()
    api_main.reset_graph()
    monkeypatch.setattr(
        "api.routers.graph_admin._rebuild_executor",
        _ImmediateExecutor(),
    )
    yield
    api_main.reset_graph()
    providers.clear_graph_lifecycle_settings_cache()


class _ImmediateExecutor:
    """Executor test double that runs submitted work synchronously."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        """
        Submit a callable for immediate execution and return a Future completed with its outcome.

        The callable is invoked synchronously; if it returns normally the Future contains the return value, and if it raises the exception the Future contains that exception.

        Parameters:
                fn: The callable to invoke.
                *args: Positional arguments forwarded to `fn`.
                **kwargs: Keyword arguments forwarded to `fn`.

        Returns:
                A Future whose result is the callable's return value, or whose exception is the exception raised by the callable.
        """
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - exercised through future exception propagation
            future.set_exception(exc)
        return future


def _authorized_app() -> Any:
    """
    Create an application whose get_current_active_user dependency is overridden to supply an active test user.

    Returns:
        ASGI app with the `get_current_active_user` dependency overridden to return a non-disabled `User` with username "operator".
    """
    app = create_app()

    async def active_user() -> User:
        """
        Provide the active test user.

        Returns:
            User: an active, non-disabled test user with username "operator".
        """
        return User(username="operator", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    return app


async def _post_rebuild() -> httpx.Response:
    """
    Send an authenticated POST request to the /api/graph/rebuild endpoint using the test ASGI app with an overridden active user.

    Returns:
        httpx.Response: The HTTP response from the POST request to /api/graph/rebuild.
    """
    transport = httpx.ASGITransport(app=_authorized_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        return await client.post("/api/graph/rebuild")


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """
    Build a file-backed SQLite database URL for the given directory and filename.

    Parameters:
        tmp_path (Path): Directory where the SQLite file will be created.
        name (str): Filename for the SQLite database (default: "asset_graph.db").

    Returns:
        database_url (str): A SQLite URL pointing to the file at `tmp_path / name`.
    """
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """
    Create and initialize the database schema used for graph persistence.

    Initializes the persistence schema required to store AssetRelationshipGraph data at the given database URL. The database engine is disposed after initialization, even if initialization fails.

    Parameters:
        database_url (str): Database connection URL where the graph persistence schema will be created.
    """
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _load_graph(database_url: str) -> AssetRelationshipGraph:
    """
    Load the persisted AssetRelationshipGraph from the database at the given URL.

    This function opens a SQLAlchemy engine and session to load the graph, and ensures the session is closed and the engine is disposed before returning.

    Parameters:
        database_url (str): SQLAlchemy database URL pointing to the persisted graph store.

    Returns:
        AssetRelationshipGraph: The graph persisted in the specified database.
    """
    engine = create_engine(database_url)
    session = create_session_factory(engine)()
    try:
        return AssetGraphRepository(session).load_graph()
    finally:
        session.close()
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """
    Persist the provided AssetRelationshipGraph into the database at the given URL.

    This saves the graph to the database and commits the transaction. The database session is closed and the engine is disposed when finished.

    Parameters:
        database_url (str): SQLAlchemy database URL for the target test database.
        graph (AssetRelationshipGraph): The asset relationship graph to persist.
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


def _equity(asset_id: str, symbol: str) -> Equity:
    """
    Create a minimal Equity asset populated with sensible defaults.

    Returns:
        Equity: An Equity with the provided id and symbol, name formatted as "<symbol> Equity", asset_class set to AssetClass.EQUITY, sector "Technology", and price 100.0.
    """
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _graph_with_asset(asset_id: str, symbol: str) -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph containing a single equity asset.

    Parameters:
        asset_id (str): The asset's unique identifier.
        symbol (str): The equity symbol.

    Returns:
        AssetRelationshipGraph: Graph containing one asset with the given id and symbol.
    """
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity(asset_id, symbol))
    return graph


def _graph_with_duplicate_events() -> AssetRelationshipGraph:
    """
    Build a graph containing a single asset and a duplicated regulatory event to simulate a contract violation.

    Returns:
        AssetRelationshipGraph: Graph with one asset and the same `RegulatoryEvent` instance present twice in its `regulatory_events` list.
    """
    graph = _graph_with_asset("DUP_ASSET", "DUP")
    event = RegulatoryEvent(
        id="DUP_EVENT",
        asset_id="DUP_ASSET",
        event_type=RegulatoryActivity.SEC_FILING,
        date="2024-01-15",
        description="duplicate filing",
        impact_score=0.1,
    )
    graph.regulatory_events = [event, event]
    return graph


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """
    Configure the graph persistence for tests by setting the ASSET_GRAPH_DATABASE_URL environment variable and clearing cached lifecycle settings.

    Parameters:
        database_url (str): The database URL to use for graph persistence.
    """
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    providers.clear_graph_lifecycle_settings_cache()


def _patch_sample_graph(
    monkeypatch: pytest.MonkeyPatch,
    graph: AssetRelationshipGraph,
) -> None:
    """
    Override providers.create_sample_graph so it returns the provided graph for the duration of the test.

    Parameters:
        monkeypatch (pytest.MonkeyPatch): Test fixture used to apply the attribute override.
        graph (AssetRelationshipGraph): The graph instance that the patched factory will return.
    """
    monkeypatch.setattr(providers, "create_sample_graph", lambda: graph)


async def _run_rebuild_with_known_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    graph: AssetRelationshipGraph,
    database_name: str = "asset_graph.db",
) -> Tuple[httpx.Response, str]:
    """
    Prepare a durable persistence backend with the provided graph and trigger an explicit rebuild.

    Parameters:
        tmp_path (Path): Temporary directory used to create the file-backed SQLite database.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture used to configure environment and patch providers.
        graph (AssetRelationshipGraph): Graph to be used as the sample/cache source for the rebuild.
        database_name (str): Filename for the SQLite database inside tmp_path. Defaults to "asset_graph.db".

    Returns:
        tuple: A pair (response, database_url) where `response` is the HTTPX response from the rebuild endpoint and `database_url` is the durable SQLite URL used for persistence.
    """
    database_url = _sqlite_url(tmp_path, database_name)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    _patch_sample_graph(monkeypatch, graph)
    return await _post_rebuild(), database_url


async def test_unauthenticated_rebuild_request_is_rejected() -> None:
    """The rebuild endpoint requires authentication."""
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        response = await client.post("/api/graph/rebuild")

    assert response.status_code == 401


@pytest.mark.parametrize("configured_value", [None, "", "   "])
async def test_unset_or_blank_persistence_returns_409_without_building(
    configured_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that an explicit rebuild request is rejected with 409 when graph persistence is unset or blank.

    Patches the rebuild graph builder to raise if invoked to ensure validation short-circuits before any build work, and asserts the response JSON contains {"detail": "Graph persistence is not configured."}.
    """
    if configured_value is not None:
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", configured_value)
    providers.clear_graph_lifecycle_settings_cache()

    def fail_build(
        _settings: providers.GraphLifecycleSettings,
    ) -> Tuple[AssetRelationshipGraph, providers.GraphRebuildSource]:
        """
        Raise an AssertionError if a rebuild attempt reaches the build stage.

        This hook is intended to ensure validation short-circuits before a build is attempted; it always raises an AssertionError with the message "build should not be attempted".

        Raises:
            AssertionError: Always raised to indicate that a build must not be attempted.
        """
        raise AssertionError("build should not be attempted")

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", fail_build)

    response = await _post_rebuild()

    assert response.status_code == 409
    assert response.json() == {"detail": "Graph persistence is not configured."}


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file::memory:?cache=shared",
        "sqlite:///file:testmem?mode=memory",
    ],
)
async def test_in_memory_sqlite_persistence_returns_409_without_building(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-durable graph persistence should fail before rebuild work starts."""
    _configure_persistence(monkeypatch, database_url)

    def fail_build(
        _settings: providers.GraphLifecycleSettings,
    ) -> Tuple[AssetRelationshipGraph, providers.GraphRebuildSource]:
        """
        Raise an AssertionError if a rebuild attempt reaches the build stage.

        This hook is intended to ensure validation short-circuits before a build is attempted; it always raises an AssertionError with the message "build should not be attempted".

        Raises:
            AssertionError: Always raised to indicate that a build must not be attempted.
        """
        raise AssertionError("build should not be attempted")

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", fail_build)

    response = await _post_rebuild()

    assert response.status_code == 409
    assert response.json() == {"detail": "Graph persistence must use a durable database."}


def test_resolve_durable_graph_persistence_url_validation(tmp_path: Path) -> None:
    """The provider resolver should distinguish unset, non-durable, and durable URLs."""
    durable_url = f"  {_sqlite_url(tmp_path)}  "

    with pytest.raises(providers.GraphPersistenceNotConfiguredError):
        providers.resolve_durable_graph_persistence_url(" ")
    with pytest.raises(providers.GraphPersistenceNonDurableError):
        providers.resolve_durable_graph_persistence_url("sqlite:///:memory:")

    assert providers.resolve_durable_graph_persistence_url(durable_url) == durable_url.strip()


async def test_explicit_rebuild_persists_sample_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A durable explicit rebuild should save and publish the sample graph."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    response = await _post_rebuild()

    saved = _load_graph(database_url)
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "persisted"
    assert body["source"] == "sample"
    assert body["asset_count"] == len(saved.assets) > 0
    assert body["relationship_count"] == sum(len(items) for items in saved.relationships.values())
    assert body["regulatory_event_count"] == len(saved.regulatory_events)
    assert api_main.get_graph().assets.keys() == saved.assets.keys()


async def test_rebuild_uses_cache_path_before_sample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GRAPH_CACHE_PATH should be the first rebuild source."""
    database_url = _sqlite_url(tmp_path)
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{}", encoding="utf-8")
    known_graph = _graph_with_asset("CACHE_ASSET", "CACHE")
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
    providers.clear_graph_lifecycle_settings_cache()
    monkeypatch.setattr(providers, "load_graph_from_cache_path", lambda *_args, **_kwargs: known_graph)

    response = await _post_rebuild()

    assert response.status_code == 200
    assert response.json()["source"] == "cache"
    assert set(_load_graph(database_url).assets) == {"CACHE_ASSET"}


async def test_rebuild_skips_absent_cache_path_for_real_data_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured but absent cache path should not be reported as cache provenance."""
    database_url = _sqlite_url(tmp_path)
    known_graph = _graph_with_asset("REAL_ASSET", "REAL")
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    monkeypatch.setenv("GRAPH_CACHE_PATH", str(tmp_path / "missing-cache.json"))
    monkeypatch.setenv("USE_REAL_DATA_FETCHER", "1")
    providers.clear_graph_lifecycle_settings_cache()

    def fail_cache_load(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """
        Assert that a cache load path was not used as the rebuild source.

        This test helper always raises an AssertionError to indicate that an absent or invalid cache path
        must not be treated as the source for rebuilding the graph.

        Raises:
            AssertionError: Always raised to signal incorrect use of a cache path as rebuild source.
        """
        raise AssertionError("absent cache path must not be used")

    monkeypatch.setattr(providers, "load_graph_from_cache_path", fail_cache_load)
    monkeypatch.setattr(providers, "load_graph_from_real_data_fetcher", lambda *_args, **_kwargs: known_graph)

    response = await _post_rebuild()

    assert response.status_code == 200
    assert response.json()["source"] == "real_data"
    assert set(_load_graph(database_url).assets) == {"REAL_ASSET"}


async def test_rebuild_uses_real_data_before_sample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """USE_REAL_DATA_FETCHER should be used when no cache path is configured."""
    database_url = _sqlite_url(tmp_path)
    known_graph = _graph_with_asset("REAL_ASSET", "REAL")
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    monkeypatch.setenv("USE_REAL_DATA_FETCHER", "1")
    providers.clear_graph_lifecycle_settings_cache()
    monkeypatch.setattr(providers, "load_graph_from_real_data_fetcher", lambda *_args, **_kwargs: known_graph)

    response = await _post_rebuild()

    assert response.status_code == 200
    assert response.json()["source"] == "real_data"
    assert set(_load_graph(database_url).assets) == {"REAL_ASSET"}


async def test_runtime_graph_updates_only_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed save must leave the runtime graph on the prior instance."""
    database_url = _sqlite_url(tmp_path)
    graph_a = _graph_with_asset("GRAPH_A", "A")
    graph_b = _graph_with_asset("GRAPH_B", "B")
    api_main.set_graph(graph_a)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    _patch_sample_graph(monkeypatch, graph_b)

    def fail_save(*_args: Any, **_kwargs: Any) -> None:
        """
        Cause an explicit save operation to fail by raising a RuntimeError.

        Raises:
            RuntimeError: Always raised with message "boom".
        """
        raise RuntimeError("boom")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save)

    response = await _post_rebuild()

    assert response.status_code == 500
    assert api_main.get_graph() is graph_a


async def test_runtime_graph_and_main_mirror_update_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful save should update both lifecycle state and api.main.graph."""
    graph_a = _graph_with_asset("GRAPH_A", "A")
    graph_b = _graph_with_asset("GRAPH_B", "B")
    api_main.set_graph(graph_a)

    response, database_url = await _run_rebuild_with_known_graph(tmp_path, monkeypatch, graph_b)

    assert response.status_code == 200
    assert graph_lifecycle.get_graph() is graph_b
    assert api_main.graph is graph_b
    assert set(_load_graph(database_url).assets) == {"GRAPH_B"}


async def test_destructive_snapshot_is_limited_to_explicit_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit rebuild should intentionally replace stale persisted graph rows."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _graph_with_asset("STALE_ASSET", "STALE"))
    _configure_persistence(monkeypatch, database_url)
    _patch_sample_graph(monkeypatch, _graph_with_asset("FRESH_ASSET", "FRESH"))

    response = await _post_rebuild()

    assert response.status_code == 200
    assert set(_load_graph(database_url).assets) == {"FRESH_ASSET"}


async def test_read_only_endpoints_do_not_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure read-only API endpoints do not persist the graph.

    Patches AssetGraphRepository.save_graph to raise if called, sets a small in-memory graph as the runtime graph, and performs GET requests against `/api/assets`, `/api/relationships`, `/api/metrics`, and `/api/visualization` to verify they return 200 without invoking persistence. Also asserts the system health check remains `healthy` or `degraded`.
    """
    api_main.set_graph(_graph_with_asset("READ_ONLY", "RO"))

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if a read-only endpoint attempts persistence."""
        raise AssertionError("read-only endpoints must not persist")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)
    monkeypatch.setattr(
        "api.routers.system._get_database_health",
        lambda: DatabaseHealthResponse(configured=True, type="sqlite", reachable=True),
    )
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        for path in ("/api/assets", "/api/relationships", "/api/metrics", "/api/visualization"):
            response = await client.get(path)
            assert response.status_code == 200, path

    from api.routers.system import detailed_health_check  # pylint: disable=import-outside-toplevel

    assert detailed_health_check().status in {"healthy", "degraded"}


def test_startup_load_does_not_overwrite_durable_graph_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Ensure startup graph load does not persist or modify the durable graph.

    Verifies that resetting and loading the runtime graph at startup does not call the repository's save method and does not change the persisted graph stored at the configured durable database URL.
    """
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _graph_with_asset("PERSISTED_ASSET", "PERSISTED"))
    _configure_persistence(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """
        Abort the operation if any attempt is made to persist during startup.

        Raises:
            AssertionError: Always raised to signal that startup load must not perform persistence.
        """
        raise AssertionError("startup load must not persist")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)

    graph_lifecycle.reset_graph()
    loaded = graph_lifecycle.get_graph()

    assert set(loaded.assets) == {"PERSISTED_ASSET"}
    assert set(_load_graph(database_url).assets) == {"PERSISTED_ASSET"}


async def test_duplicate_regulatory_events_preserve_prior_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate event IDs should fail before destructive replacement."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _graph_with_asset("ORIGINAL_ASSET", "ORIGINAL"))
    _configure_persistence(monkeypatch, database_url)
    _patch_sample_graph(monkeypatch, _graph_with_duplicate_events())

    response = await _post_rebuild()

    assert response.status_code == 500
    assert set(_load_graph(database_url).assets) == {"ORIGINAL_ASSET"}


class _TrackingSession:
    """Proxy a SQLAlchemy session while tracking rollback and close calls."""

    def __init__(
        self,
        session: Any,
        mark_rollback: Callable[[], None],
        mark_close: Callable[[], None],
    ) -> None:
        """
        Create a proxy around a DB session that delegates operations to the given session and records when rollback or close are invoked.

        Parameters:
            session (Any): The underlying session object to proxy.
            mark_rollback (Callable[[], None]): Callback invoked when a rollback is performed.
            mark_close (Callable[[], None]): Callback invoked when the session is closed.
        """
        self._session = session
        self._mark_rollback = mark_rollback
        self._mark_close = mark_close

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped session."""
        return getattr(self._session, name)

    def rollback(self) -> None:
        """Track and perform rollback."""
        self._mark_rollback()
        self._session.rollback()

    def close(self) -> None:
        """
        Record that the session was closed and close the underlying SQLAlchemy session.
        """
        self._mark_close()
        self._session.close()


def test_save_failure_rolls_back_closes_and_disposes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider save helper should clean up the session and engine on failure."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    rollback_calls = 0
    close_calls = 0
    dispose_calls = 0
    real_create_session_factory = providers.create_session_factory

    def mark_rollback() -> None:
        """
        Record that a rollback was invoked by incrementing the tracked rollback counter.

        Increments the enclosed `rollback_calls` counter to indicate a rollback occurred.
        """
        nonlocal rollback_calls
        rollback_calls += 1

    def mark_close() -> None:
        """
        Record that the session's close method was invoked by incrementing the tracked close counter.
        """
        nonlocal close_calls
        close_calls += 1

    def tracking_session_factory(engine: Any) -> Any:
        """
        Create a session factory that produces TrackingSession instances which record whether rollback or close were called.

        Parameters:
            engine (Any): The SQLAlchemy engine or engine-like object used to create sessions.

        Returns:
            make_session (Callable[[], _TrackingSession]): A zero-argument factory that returns a `_TrackingSession` wrapping a new real session and tracking rollback/close activity.
        """
        real_factory = real_create_session_factory(engine)

        def make_session() -> _TrackingSession:
            """
            Create a _TrackingSession that wraps a freshly created SQLAlchemy session and records whether rollback and close are invoked.

            Returns:
                _TrackingSession: A proxy session that delegates to the underlying session produced by `real_factory()` and marks when rollback or close are called.
            """
            return _TrackingSession(real_factory(), mark_rollback, mark_close)

        return make_session

    def fail_save(*_args: Any, **_kwargs: Any) -> None:
        """
        Test helper that immediately fails by raising a RuntimeError.

        Always raises RuntimeError with the message "boom".
        Raises:
            RuntimeError: Always raised with message "boom".
        """
        raise RuntimeError("boom")

    class _EngineProxy:
        """Proxy an engine while tracking dispose."""

        def __init__(self, engine: Any) -> None:
            """
            Initialize the tracking wrapper with the associated SQLAlchemy engine.

            Parameters:
                engine (Any): The SQLAlchemy engine associated with the session; stored on the instance for use by tracking/cleanup operations.
            """
            self._engine = engine

        def __getattr__(self, name: str) -> Any:
            """
            Delegate attribute access to the wrapped engine.

            Parameters:
                name (str): Attribute name to retrieve.

            Returns:
                Any: The attribute value from the underlying engine.
            """
            return getattr(self._engine, name)

        def dispose(self) -> None:
            """
            Dispose the underlying SQLAlchemy engine and record that disposal occurred.

            Increments the surrounding `dispose_calls` counter and calls `dispose()` on the instance's `_engine` to release engine resources.
            """
            nonlocal dispose_calls
            dispose_calls += 1
            self._engine.dispose()

    real_create_engine = providers.create_engine_from_url
    monkeypatch.setattr(providers, "create_session_factory", tracking_session_factory)
    monkeypatch.setattr(providers, "create_engine_from_url", lambda url: _EngineProxy(real_create_engine(url)))
    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save)

    with pytest.raises(providers.GraphPersistenceSaveError):
        providers.save_graph_to_persistence(database_url, _graph_with_asset("FAIL", "FAIL"))

    assert rollback_calls == 1
    assert close_calls == 1
    assert dispose_calls == 1


def test_engine_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Verifies that an engine creation failure is reported without exposing the database URL or credentials.

    Asserts that a GraphPersistenceSaveError is raised with a sanitized message and that neither the raw URL nor sensitive credentials appear in the exception text or in logged error output.
    """
    raw_url = "postgresql://user:secret@example.invalid/db"

    def fail_create_engine(_database_url: str) -> Any:
        """
        Simulate an engine creation failure for the given database URL.

        Parameters:
            _database_url (str): The database connection URL that the engine creation was attempted with.

        Raises:
            RuntimeError: Always raised indicating the connection to the provided database URL failed.
        """
        raise RuntimeError(f"cannot connect to {raw_url}")

    monkeypatch.setattr(providers, "create_engine_from_url", fail_create_engine)

    with caplog.at_level(logging.ERROR), pytest.raises(providers.GraphPersistenceSaveError) as exc_info:
        providers.save_graph_to_persistence(raw_url, _graph_with_asset("FAIL", "FAIL"))

    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert str(exc_info.value) == "Failed to persist rebuilt graph."
    assert raw_url not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)
    assert raw_url not in log_output
    assert "secret" not in log_output


async def test_failure_response_and_logs_do_not_leak_database_url(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Configured persistence failures should not expose URLs or credentials."""
    raw_url = "postgresql://user:secret@example.invalid/db"
    _configure_persistence(monkeypatch, raw_url)

    def fail_save(_database_url: str | None, _graph: AssetRelationshipGraph) -> None:
        """
        Simulate a sanitized provider failure when attempting to save a rebuilt graph.

        Raises:
            providers.GraphPersistenceSaveError: Always raised to indicate a persistence save failure without exposing sensitive details.
        """
        logging.getLogger("api.graph_lifecycle_providers").error("Failed to persist rebuilt graph: RuntimeError")
        raise providers.GraphPersistenceSaveError("Failed to persist rebuilt graph.")

    monkeypatch.setattr("api.routers.graph_admin.save_graph_to_persistence", fail_save)

    with caplog.at_level(logging.ERROR):
        response = await _post_rebuild()

    response_text = response.text
    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert response.status_code == 500
    assert raw_url not in response_text
    assert "secret" not in response_text
    assert raw_url not in log_output
    assert "secret" not in log_output
