"""Shared helpers for restart-recovery integration tests."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.graph_lifecycle_providers import stage_graph_snapshot
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_repository import (
    FinalizeProjectionPublicationRequest,
    RelationshipAssertionRepository,
)
from src.data.relationship_projection_persistence import PersistProjectionRequest
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import ProjectionRevision
from src.logic.snapshot_attestation import compute_repository_snapshot_hash
from src.models.financial_models import AssetClass, Equity
from tests.integration.facade import (
    AssetGraphRepository,
    create_session_factory,
    init_db,
    session_scope,
)

LOCK_NAME = "graph_rebuild"
LOCK_TTL = 300
_ASSET_SPECS: tuple[tuple[str, str, AssetClass, str, float], ...] = (
    ("ASSET_A", "ASSET_A Equity", AssetClass.EQUITY, "Technology", 100.0),
    ("ASSET_B", "ASSET_B Equity", AssetClass.EQUITY, "Technology", 100.0),
    ("ASSET_C", "ASSET_C Equity", AssetClass.EQUITY, "Technology", 100.0),
)
_RELATIONSHIP_SPECS: tuple[tuple[str, str, str, float], ...] = (
    ("ASSET_A", "ASSET_B", "observed", 0.4),
    ("ASSET_B", "ASSET_C", "observed", 0.6),
)


def database(tmp_path: Path) -> tuple[str, Engine, sessionmaker[Session]]:
    """Create an initialized restart-recovery database and session factory.

    The returned URL is suitable for startup configuration, while the engine and
    session factory let tests seed persisted graph state and dispose resources.
    """
    db_url = f"sqlite:///{tmp_path / 'restart-recovery.db'}"
    engine = create_engine(db_url)
    init_db(engine)
    return db_url, engine, create_session_factory(engine)


def graph() -> AssetRelationshipGraph:
    """Build the deterministic graph expected to survive restart recovery.

    The graph intentionally includes three assets and two directed relationships
    so tests can verify persistence fidelity across startup load boundaries.
    """
    asset_graph = AssetRelationshipGraph()
    for asset_id, name, asset_class, sector, price in _ASSET_SPECS:
        asset_graph.add_asset(
            Equity(
                id=asset_id,
                symbol=asset_id,
                name=name,
                asset_class=asset_class,
                sector=sector,
                price=price,
            )
        )
    for source_id, target_id, relationship_type, strength in _RELATIONSHIP_SPECS:
        asset_graph.add_relationship(
            source_id,
            target_id,
            relationship_type,
            strength,
            bidirectional=False,
        )
    return asset_graph


def publish_attested_graph(
    session_factory: sessionmaker[Session] | Any,
    asset_graph: AssetRelationshipGraph,
    *,
    job_id: str = "job-restart-recovery",
    execution_id: str = "exec-restart-recovery",
    requested_by: str = "restart-recovery-fixture",
    published_at: datetime | None = None,
) -> str:
    """Persist and publish an attested graph snapshot through production publication boundaries."""
    now = published_at or (datetime.now(timezone.utc) - timedelta(minutes=5))
    with session_scope(session_factory) as session:
        job = RebuildJobORM(
            job_id=job_id,
            requested_by=requested_by,
            status="running",
            source="test",
            created_at=now,
            updated_at=now,
            started_at=now,
            execution_id=execution_id,
        )
        session.add(job)
        session.commit()

    with session_scope(session_factory) as session:
        stage_graph_snapshot(session, asset_graph)
        session.flush()
        snapshot_sha256 = compute_repository_snapshot_hash(AssetGraphRepository(session))

        revision = ProjectionRevision(
            purpose="test-current",
            effective_at=now,
            known_at=now,
            contract_version="grac-v1",
            projector_version="projector-v1",
            edge_set_hash="0" * 64,
            projection_hash="0" * 64,
            edges=(),
            governed_scopes=(),
        )
        assertion_repo = RelationshipAssertionRepository(session)
        assertion_repo.finalize_projection_publication(
            FinalizeProjectionPublicationRequest(
                projection=PersistProjectionRequest(
                    revision=revision,
                    revision_id=f"rev-{uuid4().hex[:8]}",
                    created_at=now,
                ),
                rebuild_job_id=job_id,
                execution_id=execution_id,
                node_count=len(asset_graph.assets),
                edge_count=sum(len(edges) for edges in asset_graph.relationships.values()),
                duration_ms=100,
                published_at=now,
                snapshot_sha256=snapshot_sha256,
            ),
            pre_success_check=lambda: None,
            pre_commit_check=lambda: None,
        )
    return snapshot_sha256


def persist_graph(session_factory: sessionmaker[Session], asset_graph: AssetRelationshipGraph) -> None:
    """Persist restart-recovery graph truth through the repository boundary."""
    publish_attested_graph(session_factory, asset_graph)


def assert_graph_contents(asset_graph: AssetRelationshipGraph) -> None:
    """Assert the restart-recovery graph loaded with full asset and edge fidelity."""
    expected_assets = {
        asset_id: (asset_id, name, asset_class, sector, price)
        for asset_id, name, asset_class, sector, price in _ASSET_SPECS
    }
    assert set(asset_graph.assets) == set(expected_assets)
    for asset_id, expected in expected_assets.items():
        asset = asset_graph.assets[asset_id]
        assert (
            asset.symbol,
            asset.name,
            asset.asset_class,
            asset.sector,
            asset.price,
        ) == expected

    relationships = {
        (source_id, target_id, relationship_type, strength)
        for source_id, edges in asset_graph.relationships.items()
        for target_id, relationship_type, strength in edges
    }
    assert relationships == set(_RELATIONSHIP_SPECS)
