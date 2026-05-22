"""Hosted-like startup and readiness persistence proofs."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest  # pylint: disable=import-error
from fastapi.testclient import TestClient  # pylint: disable=import-error

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
from api.app_factory import create_app
from api.auth import User, get_current_active_user
from api.routers import graph_admin
from src.config.settings import get_settings
from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

pytestmark = pytest.mark.integration


def _reset_runtime_graph_state() -> None:
    """Reset lifecycle graph state and any already-imported legacy api.main mirror."""
    graph_lifecycle.reset_graph()
    api_main = sys.modules.get("api.main")
    if api_main is not None and hasattr(api_main, "graph"):
        api_main.graph = None  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch):
    """Reset graph environment, runtime state, and settings cache."""
    for name in (
        "ASSET_GRAPH_DATABASE_URL",
        "GRAPH_CACHE_PATH",
        "REAL_DATA_CACHE_PATH",
        "USE_REAL_DATA_FETCHER",
        "ADMIN_USERNAME",
    ):
        monkeypatch.delenv(name, raising=False)
    providers.clear_graph_lifecycle_settings_cache()
    _reset_runtime_graph_state()
    yield
    _reset_runtime_graph_state()
    providers.clear_graph_lifecycle_settings_cache()


def _sqlite_url(tmp_path: Path, name: str = "hosted_graph.db") -> str:
    """Build a file-backed SQLite database URL."""
    return f"sqlite:///{tmp_path / name}"


def _init_empty_db(database_url: str) -> None:
    """Create graph persistence schema in an empty database."""
    engine = providers.create_engine_from_url(database_url)
    try:
        init_db(engine)
    finally:
        engine.dispose()


def _save_graph(database_url: str, graph: AssetRelationshipGraph) -> None:
    """Persist a graph into the test database."""
    engine = providers.create_engine_from_url(database_url)
    init_db(engine)
    session = create_session_factory(engine)()
    try:
        AssetGraphRepository(session).save_graph(graph)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _create_test_equity(asset_id: str, symbol: str) -> Equity:
    """Build a minimal equity asset."""
    return Equity(
        id=asset_id,
        symbol=symbol,
        name=f"{symbol} Equity",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=100.0,
    )


def _seeded_hosted_graph() -> AssetRelationshipGraph:
    """Build a persisted graph with asymmetric reverse edges and one event."""
    graph = AssetRelationshipGraph()
    graph.add_asset(_create_test_equity("HOSTED_A", "HA"))
    graph.add_asset(_create_test_equity("HOSTED_B", "HB"))
    graph.add_relationship("HOSTED_A", "HOSTED_B", "directed_alpha", 0.4)
    graph.add_relationship("HOSTED_B", "HOSTED_A", "directed_alpha", 0.9)
    graph.add_regulatory_event(
        RegulatoryEvent(
            id="HOSTED_EVENT_A",
            asset_id="HOSTED_A",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-01-15",
            description="Hosted startup regulatory event",
            impact_score=0.2,
            related_assets=["HOSTED_B"],
        )
    )
    return graph


def _configure_persistence(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """Configure durable graph persistence URL for startup."""
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    providers.clear_graph_lifecycle_settings_cache()
    _reset_runtime_graph_state()


def _authorized_active_user_app(monkeypatch: pytest.MonkeyPatch):
    """Create an app with an active authenticated test user and pinned admin configuration."""
    # Force the environment state
    monkeypatch.setenv("ADMIN_USERNAME", "admin")

    # Ensure create_app() picks up the newly injected environment variable
    get_settings.cache_clear()

    app = create_app()

    def active_user() -> User:
        """Return a generic authenticated test user for the existing rebuild auth contract."""
        return User(username="admin", disabled=False)

    app.dependency_overrides[get_current_active_user] = active_user
    return app


@dataclass
class _DisposeTracker:
    """Track engine disposal calls."""

    dispose_calls: int = 0


class _EngineProxy:
    """Track startup engine disposal while proxying SQLAlchemy engine methods."""

    def __init__(self, engine: Any, tracker: _DisposeTracker) -> None:
        """Wrap an engine and track dispose calls."""
        self._engine = engine
        self._tracker = tracker

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped engine."""
        return getattr(self._engine, name)

    def dispose(self) -> None:
        """Track and forward dispose calls."""
        self._tracker.dispose_calls += 1
        self._engine.dispose()


def _relationship_strengths(relationships: list[dict[str, Any]]) -> dict[tuple[str, str, str], float]:
    """Index directed relationships by source, target, and type."""
    return {
        (
            relationship["source_id"],
            relationship["target_id"],
            relationship["relationship_type"],
        ): relationship["strength"]
        for relationship in relationships
    }


def _walk_strings(value: Any) -> Iterator[str]:
    """Recursively extract all string values and keys from JSON-like data."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def test_hosted_startup_loads_persisted_graph_truth_via_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Hosted-like startup should load persisted graph truth and bypass fallback generation."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _seeded_hosted_graph())
    _configure_persistence(monkeypatch, database_url)

    def fail_fallback_generation(*_args: Any, **_kwargs: Any) -> AssetRelationshipGraph:
        """Fail the test if startup unexpectedly falls back to any generation path."""
        raise AssertionError("Fallback generation triggered unexpectedly")

    monkeypatch.setattr(providers, "create_sample_graph", fail_fallback_generation)
    monkeypatch.setattr(providers, "load_graph_from_cache_path", fail_fallback_generation)
    monkeypatch.setattr(providers, "load_graph_from_real_data_fetcher", fail_fallback_generation)

    with caplog.at_level(logging.INFO), TestClient(create_app()) as client:
        detailed = client.get("/api/health/detailed")
        assets = client.get("/api/assets", params={"per_page": 1000})
        relationships = client.get("/api/relationships")

    assert detailed.status_code == 200
    assert assets.status_code == 200
    assert relationships.status_code == 200

    graph_payload = detailed.json()["graph"]
    assert graph_payload["available"] is True
    assert graph_payload["asset_count"] == 2
    assert graph_payload["relationship_count"] == 2

    asset_ids = {item["id"] for item in assets.json()["items"]}
    assert {"HOSTED_A", "HOSTED_B"} <= asset_ids

    relationship_payload = relationships.json()
    relationship_strengths = _relationship_strengths(relationship_payload)
    assert relationship_strengths[("HOSTED_A", "HOSTED_B", "directed_alpha")] == pytest.approx(0.4)
    assert relationship_strengths[("HOSTED_B", "HOSTED_A", "directed_alpha")] == pytest.approx(0.9)

    loaded = graph_lifecycle.get_graph()
    assert [event.id for event in loaded.regulatory_events] == ["HOSTED_EVENT_A"]

    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert "Graph startup source: persisted_graph_store" in log_output


def test_startup_persistence_engine_is_short_lived_and_disposed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup persisted-load engine should be disposed after use."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _seeded_hosted_graph())
    _configure_persistence(monkeypatch, database_url)

    real_create_engine = providers.create_engine_from_url
    tracker = _DisposeTracker()

    def tracking_create_engine(*args: Any, **kwargs: Any) -> _EngineProxy:
        """Return a dispose-tracking engine proxy."""
        return _EngineProxy(real_create_engine(*args, **kwargs), tracker)

    monkeypatch.setattr(providers, "create_engine_from_url", tracking_create_engine)

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert tracker.dispose_calls == 1


def test_readiness_endpoints_do_not_save_or_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness/read-only routes should not persist or trigger rebuild."""
    database_url = _sqlite_url(tmp_path)
    _save_graph(database_url, _seeded_hosted_graph())
    _configure_persistence(monkeypatch, database_url)

    def fail_save_graph(*_args: Any, **_kwargs: Any) -> None:
        """Fail if any read-only endpoint attempts persistence."""
        raise AssertionError("readiness/read-only endpoints must not save graph truth")

    def fail_rebuild(*_args: Any, **_kwargs: Any) -> None:
        """Fail if readiness ever attempts explicit rebuild behavior."""
        raise AssertionError("readiness endpoints must not trigger explicit rebuild")

    monkeypatch.setattr(AssetGraphRepository, "save_graph", fail_save_graph)
    monkeypatch.setattr(graph_admin, "_perform_rebuild_and_persist_sync", fail_rebuild)

    with TestClient(create_app()) as client:
        for path in ("/api/health", "/api/health/detailed", "/api/assets", "/api/relationships"):
            response = client.get(path)
            assert response.status_code == 200, path


def test_hosted_detailed_readiness_output_is_secret_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detailed readiness must remain bounded and non-secret in hosted-like mode."""
    database_url = _sqlite_url(tmp_path, "hosted-secret-safe.db")
    _save_graph(database_url, _seeded_hosted_graph())
    _configure_persistence(monkeypatch, database_url)

    with TestClient(create_app()) as client:
        response = client.get("/api/health/detailed")

    assert response.status_code == 200
    payload = response.json()

    # Verify expected contract shape
    assert set(payload) == {"status", "graph", "database"}
    assert set(payload["graph"]) == {
        "available",
        "lifecycle_state",
        "asset_count",
        "relationship_count",
    }

    # Recursively scan for sensitive values
    joined = " ".join(_walk_strings(payload)).lower()
    for forbidden in (
        "asset_graph_database_url",
        "database_url",
        database_url.lower(),
        str(tmp_path).lower(),
        "password",
        "secret",
    ):
        assert forbidden not in joined


def test_promotion_gate_sequence_rebuild_restart_and_persisted_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promotion gate sequence should prove persisted startup and configured durable graph persistence."""
    database_url = _sqlite_url(tmp_path, "promotion-gate.db")
    _init_empty_db(database_url)
    _configure_persistence(monkeypatch, database_url)

    with TestClient(_authorized_active_user_app(monkeypatch)) as client:
        rebuild_response = client.post("/api/graph/rebuild")

    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["status"] == "persisted"

    persisted_asset_count = rebuild_payload["asset_count"]
    persisted_relationship_count = rebuild_payload["relationship_count"]

    # Simulate restart by clearing runtime graph state before startup checks.
    _reset_runtime_graph_state()

    with TestClient(create_app()) as client:
        detailed_response = client.get("/api/health/detailed")

    assert detailed_response.status_code == 200
    payload = detailed_response.json()
    assert payload["status"] == "healthy"
    assert payload["graph_persistence_configured"] is True
    assert payload["graph"]["graph_startup_source"] == "persisted_graph_store"
    assert payload["graph"]["asset_count"] == persisted_asset_count
    assert payload["graph"]["relationship_count"] == persisted_relationship_count


def test_unreachable_persistence_fails_startup_with_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unreachable configured persistence should fail startup and avoid leaking connection secrets."""
    raw_url = "postgresql://user:secret@example.invalid/blackhole"
    _configure_persistence(monkeypatch, raw_url)

    def fail_create_engine(_url: str) -> Any:
        """Simulate a driver failure containing sensitive connection details."""
        raise RuntimeError(f"driver failure for {raw_url}")

    import src.data.database

    monkeypatch.setattr(src.data.database, "create_engine_from_url", fail_create_engine)
    monkeypatch.setattr(providers, "create_engine_from_url", fail_create_engine)

    startup_error = "Failed to load persisted graph during startup"
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(RuntimeError, match=startup_error) as exc_info,
        TestClient(create_app()),
    ):
        pass

    message = str(exc_info.value)
    assert raw_url not in message
    assert "secret" not in message
    assert "user" not in message

    # Verify logs also do not leak sensitive data
    log_output = " ".join(record.getMessage() for record in caplog.records)
    assert raw_url not in log_output
    assert "secret" not in log_output
