"""Tests for explicit graph rebuild persistence."""

# NOSONAR: Integration tests intentionally exercise DB/repository/API wiring.

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, Future
from pathlib import Path
from typing import Any

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException  # pylint: disable=import-error
from sqlalchemy import create_engine  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
import api.main as api_main
from api.app_factory import create_app
from api.auth import User
from api.routers import graph_admin
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset graph environment, caches, runtime state, and rebuild execution."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
    ):
        monkeypatch.delenv(name, raising=False)
    providers.clear_graph_lifecycle_settings_cache()
    api_main.reset_graph()
    monkeypatch.setattr("api.routers.graph_admin._REBUILD_RUNTIME.executor", _ImmediateExecutor())
    yield
    api_main.reset_graph()
    providers.clear_graph_lifecycle_settings_cache()


class _ImmediateExecutor(Executor):
    """Executor test double that runs submitted work synchronously."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        """Run submitted work immediately and return a completed Future."""
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - exercised through future exception propagation
            future.set_exception(exc)
        return future

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:  # pylint: disable=unused-argument
        """Match the ThreadPoolExecutor shutdown API."""


class _RouteResult:
    """Small response-like wrapper for direct route calls."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        """Create a route result."""
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> dict[str, Any]:
        """Return the response body."""
        return self._body


async def _post_rebuild() -> _RouteResult:
    """Invoke the authenticated graph rebuild route."""
    try:
        body = await graph_admin.rebuild_graph(User(username="operator", disabled=False))
    except HTTPException as exc:
        return _RouteResult(exc.status_code, {"detail": exc.detail})
    return _RouteResult(200, body.model_dump())


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """Build a file-backed SQLite database URL."""
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """Create the graph persistence schema in an empty database."""
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _load_graph(database_url: str) -> AssetRelationshipGraph:
    """Load the persisted graph from a database URL."""
    engine = create_engine(database_url)
    session = create_session_factory(engine)()
    try:
        return AssetGraphRepository(session).load_graph()
    finally:
        session.close()
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """Persist a graph into a test database."""
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
    """Create a minimal Equity asset."""
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _graph_with_asset(asset_id: str, symbol: str) -> AssetRelationshipGraph:
    """Create a graph containing a single equity asset."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity(asset_id, symbol))
    return graph


def _graph_with_duplicate_events() -> AssetRelationshipGraph:
    """Build a graph containing a duplicated regulatory event."""
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
    """Configure graph persistence for tests."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    providers.clear_graph_lifecycle_settings_cache()


def _patch_sample_graph(
    monkeypatch: pytest.MonkeyPatch,
    graph: AssetRelationshipGraph,
) -> None:
    """Patch the sample graph source to return the provided graph."""
    monkeypatch.setattr(providers, "create_sample_graph", lambda: graph)


def _prepare_rebuild_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    database_name: str = "asset_graph.db",
    existing_graph: AssetRelationshipGraph | None = None,
) -> str:
    """Prepare durable graph persistence and return its URL."""
    database_url = _sqlite_url(tmp_path, database_name)
    if existing_graph is None:
        _init_empty_db(database_url)
    else:
        _save_graph(database_url, existing_graph)
    _configure_persistence(monkeypatch, database_url)
    return database_url


async def _run_rebuild_with_known_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    graph: AssetRelationshipGraph,
    database_name: str = "asset_graph.db",
    existing_graph: AssetRelationshipGraph | None = None,
) -> tuple[_RouteResult, str]:
    """Configure durable persistence, patch rebuild source, and post rebuild."""
    database_url = _prepare_rebuild_database(
        tmp_path,
        monkeypatch,
        database_name=database_name,
        existing_graph=existing_graph,
    )
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
    """Unset persistence should fail before rebuild work starts."""
    if configured_value is not None:
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", configured_value)
    providers.clear_graph_lifecycle_settings_cache()

    def fail_build(
        _settings: providers.GraphLifecycleSettings,
    ) -> tuple[AssetRelationshipGraph, providers.GraphRebuildSource]:
        """Fail if validation does not short-circuit."""
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
    ) -> tuple[AssetRelationshipGraph, providers.GraphRebuildSource]:
        """Fail if validation does not short-circuit."""
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
    database_url = _prepare_rebuild_database(tmp_path, monkeypatch)

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
    database_url = _prepare_rebuild_database(tmp_path, monkeypatch)
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{}", encoding="utf-8")
    known_graph = _graph_with_asset("CACHE_ASSET", "CACHE")
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
    database_url = _prepare_rebuild_database(tmp_path, monkeypatch)
    known_graph = _graph_with_asset("REAL_ASSET", "REAL")
    monkeypatch.setenv("GRAPH_CACHE_PATH", str(tmp_path / "missing-cache.json"))
    monkeypatch.setenv("USE_REAL_DATA_FETCHER", "1")
    providers.clear_graph_lifecycle_settings_cache()

    def fail_cache_load(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Fail if an absent cache path is treated as a rebuild source."""
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
    database_url = _prepare_rebuild_database(tmp_path, monkeypatch)
    known_graph = _graph_with_asset("REAL_ASSET", "REAL")
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
        """Cause explicit save to fail."""
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
    response, database_url = await _run_rebuild_with_known_graph(
        tmp_path,
        monkeypatch,
        _graph_with_asset("FRESH_ASSET", "FRESH"),
        existing_graph=_graph_with_asset("STALE_ASSET", "STALE"),
    )

    assert response.status_code == 200
    assert set(_load_graph(database_url).assets) == {"FRESH_ASSET"}


async def test_read_only_endpoints_do_not_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read-only API endpoints should not persist the graph."""
    api_main.set_graph(_graph_with_asset("READ_ONLY", "RO"))

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if a read-only endpoint attempts persistence."""
        raise AssertionError("read-only endpoints must not persist")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        for path in ("/api/assets", "/api/relationships", "/api/metrics", "/api/visualization"):
            response = await client.get(path)
            assert response.status_code == 200, path


def test_startup_load_does_not_overwrite_durable_graph_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup graph load must not overwrite persisted graph truth."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _graph_with_asset("PERSISTED_ASSET", "PERSISTED"))
    _configure_persistence(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if startup load persists."""
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
    response, database_url = await _run_rebuild_with_known_graph(
        tmp_path,
        monkeypatch,
        _graph_with_duplicate_events(),
        existing_graph=_graph_with_asset("ORIGINAL_ASSET", "ORIGINAL"),
    )

    assert response.status_code == 500
    assert set(_load_graph(database_url).assets) == {"ORIGINAL_ASSET"}


class _TrackingSession:
    """Proxy a SQLAlchemy session while tracking rollback and close calls."""

    def __init__(
        self,
        session: Any,
        tracker: _SaveFailureTracker,
        *,
        rollback_raises: bool = False,
    ) -> None:
        """Create a DB session proxy that records cleanup calls."""
        self._session = session
        self._tracker = tracker
        self._rollback_raises = rollback_raises

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped session."""
        return getattr(self._session, name)

    def rollback(self) -> None:
        """Track and perform rollback."""
        self._tracker.rollback_calls += 1
        if self._rollback_raises:
            raise RuntimeError("rollback failed with sensitive detail")
        self._session.rollback()

    def close(self) -> None:
        """Track and close the wrapped session."""
        self._tracker.close_calls += 1
        self._session.close()


class _EngineProxy:
    """Proxy an engine while tracking dispose."""

    def __init__(self, engine: Any, tracker: _SaveFailureTracker) -> None:
        """Create an engine proxy."""
        self._engine = engine
        self._tracker = tracker

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped engine."""
        return getattr(self._engine, name)

    def dispose(self) -> None:
        """Track and dispose the wrapped engine."""
        self._tracker.dispose_calls += 1
        self._engine.dispose()


class _SaveFailureTracker:
    """Track graph persistence cleanup calls."""

    def __init__(self) -> None:
        """Create zeroed cleanup counters."""
        self.rollback_calls = 0
        self.close_calls = 0
        self.dispose_calls = 0


def _install_save_failure_tracking(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rollback_raises: bool = False,
) -> _SaveFailureTracker:
    """Install persistence tracking and return the tracker."""
    tracker = _SaveFailureTracker()
    real_create_session_factory = providers.create_session_factory

    def tracking_session_factory(engine: Any) -> Any:
        """Create tracking sessions from the real session factory."""
        real_factory = real_create_session_factory(engine)

        def make_session() -> _TrackingSession:
            """Create a tracking session."""
            return _TrackingSession(
                real_factory(),
                tracker,
                rollback_raises=rollback_raises,
            )

        return make_session

    def fail_save(*_args: Any, **_kwargs: Any) -> None:
        """Fail graph persistence."""
        raise RuntimeError("boom")

    real_create_engine = providers.create_engine_from_url
    monkeypatch.setattr(providers, "create_session_factory", tracking_session_factory)
    monkeypatch.setattr(
        providers,
        "create_engine_from_url",
        lambda url: _EngineProxy(real_create_engine(url), tracker),
    )
    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save)
    return tracker


def test_save_failure_rolls_back_closes_and_disposes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The save helper should clean up the session and engine on failure."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    tracker = _install_save_failure_tracking(monkeypatch)

    with pytest.raises(providers.GraphPersistenceSaveError):
        providers.save_graph_to_persistence(database_url, _graph_with_asset("FAIL", "FAIL"))

    assert tracker.rollback_calls == 1
    assert tracker.close_calls == 1
    assert tracker.dispose_calls == 1


def test_save_failure_sanitizes_rollback_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rollback failure should not replace the sanitized save error."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    tracker = _install_save_failure_tracking(monkeypatch, rollback_raises=True)

    with pytest.raises(providers.GraphPersistenceSaveError) as exc_info:
        providers.save_graph_to_persistence(database_url, _graph_with_asset("FAIL", "FAIL"))

    assert str(exc_info.value) == "Failed to persist rebuilt graph."
    assert tracker.rollback_calls == 1
    assert tracker.close_calls == 1
    assert tracker.dispose_calls == 1


def test_engine_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Engine creation failures should not expose URLs or credentials."""
    raw_url = "postgresql://user:secret@example.invalid/db"

    def fail_create_engine(_database_url: str) -> Any:
        """Simulate an engine creation failure."""
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
        """Simulate a sanitized provider failure."""
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


async def test_unexpected_rebuild_failure_returns_sanitized_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpected rebuild failures should use the route's generic 500."""
    raw_detail = "sensitive rebuild detail"
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    def fail_build(_settings: providers.GraphLifecycleSettings) -> Any:
        """Raise an unexpected rebuild error."""
        raise RuntimeError(raw_detail)

    monkeypatch.setattr("api.routers.graph_admin.build_rebuild_graph", fail_build)

    with caplog.at_level(logging.ERROR):
        response = await _post_rebuild()

    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert response.status_code == 500
    assert response.json() == {"detail": "Graph rebuild failed."}
    assert raw_detail not in response.text
    assert raw_detail not in log_output
