"""Integrated restart-recovery coverage helpers for startup, RecoveryGate, lock, and durable graph load."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as graph_lifecycle_providers
from src.data.db_models import RebuildJobORM
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity
from tests.integration.facade import (
    AssetGraphRepository,
    create_session_factory,
    init_db,
    session_scope,
)

pytestmark = pytest.mark.integration

_LOCK_TTL = 300
UTC = timezone.utc


@pytest.fixture(autouse=True)
def reset_graph_lifecycle(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    graph_lifecycle.reset_graph()
    yield
    graph_lifecycle.reset_graph()
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()


def _database(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'restart-recovery.db'}"
    engine = create_engine(db_url)
    init_db(engine)
    return db_url, engine, create_session_factory(engine)


def _graph() -> AssetRelationshipGraph:
    graph = AssetRelationshipGraph()
    for asset_id in ("ASSET_A", "ASSET_B", "ASSET_C"):
        graph.add_asset(
            Equity(
                id=asset_id,
                symbol=asset_id,
                name=f"{asset_id} Equity",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )
        )
    graph.add_relationship("ASSET_A", "ASSET_B", "observed", 0.4, bidirectional=False)
    graph.add_relationship("ASSET_B", "ASSET_C", "observed", 0.6, bidirectional=False)
    return graph


def _persist_graph(session_factory, graph: AssetRelationshipGraph) -> None:
    with session_scope(session_factory) as session:
        AssetGraphRepository(session).save_graph(graph)


def _assert_graph_contents(graph: AssetRelationshipGraph) -> None:
    assert set(graph.assets) == {"ASSET_A", "ASSET_B", "ASSET_C"}
    assert graph.assets["ASSET_A"].name == "ASSET_A Equity"
    assert graph.assets["ASSET_A"].price == pytest.approx(100.0)
    assert sum(len(edges) for edges in graph.relationships.values()) == 2


def _create_stale_running_job(session_factory) -> str:
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by="stale-owner-test")
        repo.mark_rebuild_job_running(job_id, "stale-exec")
        repo.update_rebuild_heartbeat(job_id, "stale-exec", "stale-worker")
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        job.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=_LOCK_TTL + 30)
        session.commit()
        return job_id


def _load_job(session_factory, job_id: str) -> RebuildJobORM:
    with session_scope(session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        session.expunge(job)
        return job
