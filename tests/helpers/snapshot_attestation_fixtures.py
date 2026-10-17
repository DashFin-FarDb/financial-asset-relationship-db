"""Shared fixtures and graph builders for snapshot attestation unit tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text

from src.data.database import configure_sqlite_engine, create_session_factory, init_db
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_repository import (
    FinalizeProjectionPublicationRequest,
    RelationshipAssertionRepository,
)
from src.data.relationship_projection_persistence import PersistProjectionRequest
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import ProjectionRevision
from src.logic.snapshot_attestation import compute_repository_snapshot_hash
from src.models.financial_models import (
    AssetClass,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)


def create_sample_equity_pair() -> tuple[Equity, Equity]:
    """Create a deterministic pair of equities (AAPL, MSFT) for testing."""
    eq_a = Equity(
        id="AAPL",
        symbol="AAPL.US",
        name="Apple Inc. Fixture",
        asset_class=AssetClass.EQUITY,
        sector="Consumer Electronics",
        price=192.25,
        currency="USD",
        market_cap=2900000000000.0,
    )
    eq_b = Equity(
        id="MSFT",
        symbol="MSFT.US",
        name="Microsoft Corporation Fixture",
        asset_class=AssetClass.EQUITY,
        sector="Software Infrastructure",
        price=415.50,
        currency="USD",
        market_cap=3150000000000.0,
    )
    return eq_a, eq_b


def create_sample_test_graph() -> AssetRelationshipGraph:
    """Create a deterministic graph with assets, relationships, and regulatory events."""
    graph = AssetRelationshipGraph()
    aapl, msft = create_sample_equity_pair()
    graph.add_asset(aapl)
    graph.add_asset(msft)
    graph.add_relationship("AAPL", "MSFT", "same_sector", 0.50, bidirectional=True)
    reg_event = RegulatoryEvent(
        id="REG-001",
        asset_id="AAPL",
        event_type=RegulatoryActivity.REGULATORY_FILING,
        date="2026-04-10",
        description="Annual 10-K filing",
        impact_score=0.10,
        related_assets=["MSFT"],
    )
    graph.add_regulatory_event(reg_event)
    return graph


def setup_disposable_sqlite_db(
    tmp_path: Path,
    prefix: str = "test_gate",
    *,
    wal_mode: bool = False,
) -> tuple[str, Any]:
    """Initialize a disposable SQLite test database with session factory."""
    db_file = tmp_path / f"{prefix}_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    if wal_mode:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()
    init_db(engine)
    session_factory = create_session_factory(engine)
    return db_url, session_factory


def publish_test_graph_snapshot(
    session: Any,
    graph: AssetRelationshipGraph | None = None,
    *,
    job_id: str | None = None,
    execution_id: str | None = None,
    revision_purpose: str = "test-current",
    duration_ms: int = 10,
) -> str:
    """Save graph and finalize projection publication for test lifecycle.

    Saves graph via AssetGraphRepository if provided, creates matching RebuildJobORM,
    finalizes projection publication via RelationshipAssertionRepository,
    and flushes pending mutations to the session without committing.

    Args:
        session: Active SQLAlchemy session.
        graph: Optional in-memory graph to stage. If None, repository must already have staged rows.
        job_id: Optional explicit rebuild job identifier. Defaults to generated ID.
        execution_id: Optional explicit execution identifier. Defaults to generated ID.
        revision_purpose: Purpose string for the projection revision.
        duration_ms: Recorded rebuild duration in milliseconds.

    Returns:
        The computed snapshot SHA-256 digest string. Caller retains commit/rollback ownership.
    """
    repo = AssetGraphRepository(session)
    if graph is not None:
        repo.save_graph(graph)
        node_count = len(graph.assets)
        edge_count = sum(len(edges) for edges in graph.relationships.values())
    else:
        session.flush()
        node_count = len(repo.list_assets())
        edge_count = len(repo.list_relationships())

    session.flush()
    digest = compute_repository_snapshot_hash(repo)
    now = datetime.now(timezone.utc)
    jid = job_id or f"job-{uuid4().hex[:8]}"
    eid = execution_id or f"exec-{uuid4().hex[:8]}"

    job = RebuildJobORM(
        job_id=jid,
        requested_by="test-operator",
        status="running",
        source="test",
        created_at=now,
        updated_at=now,
        started_at=now,
        execution_id=eid,
    )
    session.add(job)
    session.flush()

    revision = ProjectionRevision(
        purpose=revision_purpose,
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
            rebuild_job_id=jid,
            execution_id=eid,
            node_count=node_count,
            edge_count=edge_count,
            duration_ms=duration_ms,
            published_at=now,
            snapshot_sha256=digest,
        ),
        pre_success_check=lambda: None,
        pre_commit_check=lambda: None,
    )
    session.flush()
    return digest
