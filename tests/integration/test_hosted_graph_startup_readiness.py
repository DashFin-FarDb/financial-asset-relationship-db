"""Hosted-like readiness tests for persisted graph startup loading."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
from api.app_factory import create_app
from api.routers import graph_admin
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_hosted_startup_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset graph lifecycle state and hosted graph persistence settings."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
    ):
        monkeypatch.delenv(name, raising=False)
    providers.clear_graph_lifecycle_settings_cache()
    graph_lifecycle.reset_graph()
    yield
    graph_admin.shutdown_rebuild_executor()
    graph_lifecycle.reset_graph()
    providers.clear_graph_lifecycle_settings_cache()


class _DisposeTrackingEngine:
    """Proxy a SQLAlchemy engine while tracking explicit dispose calls."""

    def __init__(self, engine: Any, record_dispose: Callable[[], None]) -> None:
        """Wrap the engine and store the dispose-call recorder."""
        self._engine = engine
        self._record_dispose = record_dispose

    def __getattr__(self, name: str) -> Any:
        """Delegate engine attributes to the wrapped engine."""
        return getattr(self._engine, name)

    def dispose(self) -> None:
        """Record and forward engine disposal."""
        self._record_dispose()
        self._engine.dispose()


def _sqlite_url(tmp_path: Path, name: str = "asset_graph.db") -> str:
    """Return a file-backed SQLite URL under the test temporary path."""
    return f"sqlite:///{tmp_path / name}"


def _equity(asset_id: str, symbol: str) -> Equity:
    """Build a minimal equity asset for hosted startup tests."""
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Hosted Technology",
        price=100.0,
    )


def _regulatory_event(event_id: str, asset_id: str, related_assets: list[str] | None = None) -> RegulatoryEvent:
    """Build a regulatory event for hosted startup tests."""
    return RegulatoryEvent(
        id=event_id,
        asset_id=asset_id,
        event_type=RegulatoryActivity.SEC_FILING,
        date="2024-01-15",
        description=f"{event_id} filing",
        impact_score=0.5,
        related_assets=related_assets or [],
    )


def _hosted_persisted_graph() -> AssetRelationshipGraph:
    """Create a deterministic graph that is distinct from generated fallback data."""
    graph = AssetRelationshipGraph()
    for asset in (
        _equity("HOSTED_A", "HSTA"),
        _equity("HOSTED_B", "HSTB"),
        _equity("HOSTED_C", "HSTC"),
    ):
        graph.add_asset(asset)
    graph.add_relationship("HOSTED_A", "HOSTED_B", "directed_alpha", 0.4)
    graph.add_relationship("HOSTED_B", "HOSTED_A", "directed_alpha", 0.9)
    graph.add_regulatory_event(_regulatory_event("HOSTED_EVENT_A", "HOSTED_A", ["HOSTED_B", "HOSTED_C"]))
    return graph


def _single_asset_graph(asset_id: str = "FALLBACK_ONLY") -> AssetRelationshipGraph:
    """Create a one-asset graph for fallback assertions."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_equity(asset_id, asset_id))
    return graph


def _init_empty_db(database_url: str) -> None:
    """Initialize the graph persistence schema without graph rows."""
    engine = create_engine(database_url)
    try:
        init_db(engine)
    finally:
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


def _load_graph(database_url: str) -> AssetRelationshipGraph:
    """Load a graph directly from the test persistence store."""
    engine = create_engine(database_url)
    session = create_session_factory(engine)()
    try:
        return AssetGraphRepository(session).load_graph()
    finally:
        session.close()
        engine.dispose()


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """Configure graph persistence and clear cached lifecycle settings."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    providers.clear_graph_lifecycle_settings_cache()
    graph_lifecycle.reset_graph()


def _poison_fallback_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if startup attempts any generated fallback graph path."""

    def fail_fallback(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Raise if fallback generation is reached unexpectedly."""
        raise AssertionError("Fallback generation triggered unexpectedly")

    monkeypatch.setattr(providers, "create_sample_graph", fail_fallback)
    monkeypatch.setattr(providers, "load_graph_from_cache_path", fail_fallback)
    monkeypatch.setattr(providers, "load_graph_from_real_data_fetcher", fail_fallback)


def _install_startup_engine_dispose_tracker(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    """Track explicit disposal of the startup persistence engine."""
    dispose_calls = 0
    real_create_engine = providers.create_engine_from_url

    def record_dispose() -> None:
        """Increment the engine-disposal counter."""
        nonlocal dispose_calls
        dispose_calls += 1

    def tracking_create_engine(database_url: str) -> _DisposeTrackingEngine:
        """Return a dispose-tracking engine proxy for startup persistence."""
        return _DisposeTrackingEngine(real_create_engine(database_url), record_dispose)

    monkeypatch.setattr(providers, "create_engine_from_url", tracking_create_engine)
    return lambda: dispose_calls


def _relationship_lookup(response_payload: list[dict[str, Any]]) -> dict[tuple[str, str, str], float]:
    """Index relationship response rows by source, target, and type."""
    return {
        (
            row["source_id"],
            row["target_id"],
            row["relationship_type"],
        ): row["strength"]
        for row in response_payload
    }


def test_hosted_startup_loads_persisted_graph_without_generated_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hosted-like startup should load persisted graph truth and not generated fallback data."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _hosted_persisted_graph())
    _configure_persistence(monkeypatch, database_url)
    _poison_fallback_sources(monkeypatch)
    dispose_count = _install_startup_engine_dispose_tracker(monkeypatch)

    with caplog.at_level(logging.INFO, logger="api.graph_lifecycle_providers"):
        with TestClient(create_app()) as client:
            readiness_response = client.get("/api/health/detailed")
            assets_response = client.get("/api/assets?per_page=1000")
            relationships_response = client.get("/api/relationships")
            loaded_graph = graph_lifecycle.get_graph()

    readiness_payload = readiness_response.json()
    asset_ids = {asset["id"] for asset in assets_response.json()["items"]}
    relationships = _relationship_lookup(relationships_response.json())

    assert readiness_response.status_code == 200
    assert readiness_payload["graph"] == {
        "available": True,
        "asset_count": 3,
        "relationship_count": 2,
    }
    assert asset_ids == {"HOSTED_A", "HOSTED_B", "HOSTED_C"}
    assert relationships[("HOSTED_A", "HOSTED_B", "directed_alpha")] == pytest.approx(0.4)
    assert relationships[("HOSTED_B", "HOSTED_A", "directed_alpha")] == pytest.approx(0.9)
    assert [event.id for event in loaded_graph.regulatory_events] == ["HOSTED_EVENT_A"]
    assert dispose_count() == 1
    assert "Loaded graph from durable persistence" in caplog.text
    assert database_url not in caplog.text


def test_readiness_and_read_only_routes_do_not_mutate_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness and read-only routes must not save or mutate graph persistence."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _hosted_persisted_graph())
    _configure_persistence(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if a read-only or readiness path attempts to persist graph data."""
        raise AssertionError("readiness and read-only routes must not call save_graph()")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)

    with TestClient(create_app()) as client:
        for path in ("/api/health", "/api/health/detailed", "/api/assets", "/api/relationships"):
            response = client.get(path)
            assert response.status_code == 200, path

    persisted_after_readiness = _load_graph(database_url)

    assert set(persisted_after_readiness.assets) == {"HOSTED_A", "HOSTED_B", "HOSTED_C"}
    assert sum(len(items) for items in persisted_after_readiness.relationships.values()) == 2
    assert [event.id for event in persisted_after_readiness.regulatory_events] == ["HOSTED_EVENT_A"]


def test_readiness_does_not_trigger_explicit_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness must remain separate from the authenticated explicit rebuild path."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _hosted_persisted_graph())
    _configure_persistence(monkeypatch, database_url)

    def fail_rebuild(*_args: Any, **_kwargs: Any) -> Any:
        """Fail if readiness attempts to run rebuild behavior."""
        raise AssertionError("readiness must not trigger graph rebuild")

    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", fail_rebuild)
    monkeypatch.setattr(graph_admin, "build_rebuild_graph", fail_rebuild)
    monkeypatch.setattr(graph_admin, "save_graph_to_persistence", fail_rebuild)

    with TestClient(create_app()) as client:
        for path in ("/api/health", "/api/health/detailed"):
            response = client.get(path)
            assert response.status_code == 200, path


def test_readiness_output_does_not_expose_graph_persistence_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detailed readiness should expose bounded counts, not persistence configuration details."""
    database_url = _sqlite_url(tmp_path, "secret-password-hostname.db")
    _save_graph(database_url, _hosted_persisted_graph())
    _configure_persistence(monkeypatch, database_url)

    with TestClient(create_app()) as client:
        response = client.get("/api/health/detailed")

    body = response.text

    assert response.status_code == 200
    assert "ASSET_GRAPH_DATABASE_URL" not in body
    assert "DATABASE_URL" not in body
    assert "sqlite:///" not in body
    assert "secret" not in body
    assert "password" not in body
    assert "hostname" not in body
    assert str(tmp_path) not in body
    assert "driver" not in body.lower()
    assert "traceback" not in body.lower()
    assert "environment" not in body
    assert "HOSTED_A" not in body
    assert "HOSTED_EVENT_A" not in body


def test_empty_configured_persistence_preserves_fallback_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty configured persistence store should fall through to existing fallback behavior."""
    database_url = _sqlite_url(tmp_path)
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)
    monkeypatch.setattr(providers, "create_sample_graph", lambda: _single_asset_graph())

    with TestClient(create_app()) as client:
        readiness_response = client.get("/api/health/detailed")
        assets_response = client.get("/api/assets?per_page=1000")

    asset_ids = {asset["id"] for asset in assets_response.json()["items"]}

    assert readiness_response.status_code == 200
    assert readiness_response.json()["graph"] == {
        "available": True,
        "asset_count": 1,
        "relationship_count": 0,
    }
    assert asset_ids == {"FALLBACK_ONLY"}


def test_unreachable_persistence_fails_startup_without_secret_leakage(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Configured but unreachable graph persistence should abort startup with sanitized text."""
    raw_url = "postgresql://user:pass@127.0.0.1:9999/blackhole"
    _configure_persistence(monkeypatch, raw_url)
    _poison_fallback_sources(monkeypatch)

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError) as exc_info:
        with TestClient(create_app()):
            pass

    exception_text = str(exc_info.value)

    assert "Failed to load persisted graph during startup" in exception_text
    for sensitive_text in (raw_url, "user:pass", "pass", "127.0.0.1", "9999", "blackhole"):
        assert sensitive_text not in exception_text
        assert sensitive_text not in caplog.text
    assert "Fallback generation triggered unexpectedly" not in caplog.text
