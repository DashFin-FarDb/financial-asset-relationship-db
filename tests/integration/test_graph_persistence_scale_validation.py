"""Representative-scale graph persistence validation."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import pytest

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as providers
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from tests.helpers.graph_scale_factory import build_scale_graph

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _sqlite_url(tmp_path: Path, name: str = "scale-validation.db") -> str:
    """Return an isolated file-backed SQLite URL."""
    return f"sqlite:///{tmp_path / name}"


def _save_graph(database_url: str, asset_count: int, relationship_count: int) -> float:
    """Persist a deterministic graph and return elapsed seconds."""
    engine = create_engine_from_url(database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        graph = build_scale_graph(
            asset_count=asset_count,
            relationship_count=relationship_count,
            prefix=f"SCALE{asset_count}",
        )
        start = time.perf_counter()
        with session_factory() as session:
            AssetGraphRepository(session).save_graph(graph)
            session.commit()
        return time.perf_counter() - start
    finally:
        engine.dispose()


def _load_graph(database_url: str):
    """Load a persisted graph from the repository."""
    engine = create_engine_from_url(database_url)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            return AssetGraphRepository(session).load_graph()
    finally:
        engine.dispose()


def _relationship_count(graph) -> int:
    """Return the number of directed relationships in a graph."""
    return sum(len(items) for items in graph.relationships.values())


def _assert_edge_strength(graph, asset_count: int, index: int, expected_strength: float, prefix: str) -> None:
    """Assert a deterministic scale edge survived the repository round trip."""
    source_index = index % asset_count
    offset = (index // asset_count) + 1
    target_index = (source_index + offset) % asset_count
    if target_index == source_index:
        target_index = (target_index + 1) % asset_count

    source = f"{prefix}_ASSET_{source_index:05d}"
    target = f"{prefix}_ASSET_{target_index:05d}"
    assert (target, "scale_test_link", expected_strength) in graph.relationships[source]


@pytest.mark.parametrize(
    ("asset_count", "relationship_count"),
    [
        (250, 1_000),
        (1_000, 5_000),
    ],
)
def test_representative_scale_graph_save_load_round_trip(
    tmp_path: Path,
    asset_count: int,
    relationship_count: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Representative graph snapshots should round-trip with exact counts and selected edge strengths."""
    database_url = _sqlite_url(tmp_path, f"round-trip-{asset_count}.db")

    with caplog.at_level(logging.INFO):
        save_seconds = _save_graph(database_url, asset_count, relationship_count)
        load_start = time.perf_counter()
        loaded = _load_graph(database_url)
        load_seconds = time.perf_counter() - load_start
        logging.getLogger(__name__).info(
            "scale_round_trip_timing asset_count=%s relationship_count=%s save_seconds=%.3f load_seconds=%.3f",
            asset_count,
            relationship_count,
            save_seconds,
            load_seconds,
        )

    assert len(loaded.assets) == asset_count
    assert _relationship_count(loaded) == relationship_count
    assert len(set(loaded.assets)) == asset_count

    prefix = f"SCALE{asset_count}"
    _assert_edge_strength(loaded, asset_count, 0, 0.01, prefix)
    _assert_edge_strength(loaded, asset_count, min(99, relationship_count - 1), 1.0, prefix)
    _assert_edge_strength(
        loaded,
        asset_count,
        relationship_count - 1,
        ((relationship_count - 1) % 100 + 1) / 100,
        prefix,
    )


def test_representative_scale_startup_load_records_baseline_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Startup should load representative persisted graph truth within a generous regression guardrail."""
    database_url = _sqlite_url(tmp_path, "startup-scale.db")
    _save_graph(database_url, 250, 1_000)
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    providers.clear_graph_lifecycle_settings_cache()
    get_settings.cache_clear()
    graph_lifecycle.reset_graph()

    start = time.perf_counter()
    with caplog.at_level(logging.INFO):
        loaded_graph, startup_source = graph_lifecycle.get_graph_with_startup_source()
    elapsed_seconds = time.perf_counter() - start

    assert startup_source is not None
    assert startup_source.source == "persisted"
    assert len(loaded_graph.assets) == 250
    assert _relationship_count(loaded_graph) == 1_000
    assert elapsed_seconds < 15.0

    logging.getLogger(__name__).info(
        "scale_startup_load_timing asset_count=250 relationship_count=1000 elapsed_seconds=%.3f",
        elapsed_seconds,
    )
    graph_lifecycle.reset_graph()


def test_representative_scale_rebuild_records_baseline_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The rebuild persistence path should handle a representative graph within a broad guardrail."""
    import api.routers.graph_admin as graph_admin

    database_url = _sqlite_url(tmp_path, "rebuild-scale.db")
    engine = create_engine_from_url(database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="scale-test")
            repo.mark_rebuild_job_running(job_id, "scale-exec")
            session.commit()
    finally:
        engine.dispose()

    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", database_url)
    get_settings.cache_clear()
    representative_graph = build_scale_graph(asset_count=250, relationship_count=1_000, prefix="REBUILD")
    monkeypatch.setattr(
        graph_admin,
        "build_rebuild_graph",
        lambda *_args, **_kwargs: (representative_graph, "sample"),
    )

    engine = create_engine_from_url(database_url)
    try:
        session_factory = create_session_factory(engine)
        lock_lost = threading.Event()
        cancel_event = threading.Event()
        start = time.perf_counter()
        with caplog.at_level(logging.INFO):
            response = graph_admin._run_rebuild_pipeline(  # pylint: disable=protected-access
                session_factory,
                get_settings(),
                database_url,
                job_id,
                "scale-exec",
                start,
                lock_lost,
                cancel_event,
            )
        elapsed_seconds = time.perf_counter() - start
    finally:
        engine.dispose()

    assert response.status == "persisted"
    assert response.asset_count == 250
    assert response.relationship_count == 1_000
    assert elapsed_seconds < 20.0
    logging.getLogger(__name__).info(
        "scale_rebuild_timing asset_count=250 relationship_count=1000 elapsed_seconds=%.3f",
        elapsed_seconds,
    )
    graph_lifecycle.reset_graph()
