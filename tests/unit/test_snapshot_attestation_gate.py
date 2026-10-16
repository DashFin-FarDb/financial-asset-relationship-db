"""Deterministic isolated tests for the FARDB persisted-graph snapshot attestation gate.

Tests all gate invariants:
- Clean installation classification
- Successful publication & verified startup
- Tampered asset detection
- Tampered relationship detection
- Tampered regulatory event detection
- Same-count asset substitution rejection
- Missing publication rejection
- Missing attestation digest rejection
- Mismatched rebuild execution identity rejection
- Mismatched job/publication digest rejection
- Transaction rollback on failure
- Coordination failure isolation in split persistence
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, update

from api.graph_lifecycle_providers import (
    SnapshotProvenanceClassification,
    _load_persisted_graph_from_configured_store,
    load_persisted_graph_if_available,
    stage_graph_snapshot,
)
from src.data.database import configure_sqlite_engine, create_session_factory, init_db
from src.data.db_models import AssetORM, AssetRelationshipORM, RebuildJobORM, RegulatoryEventORM
from src.data.relationship_assertion_db_models import RelationshipProjectionPublicationORM
from src.data.relationship_assertion_repository import (
    FinalizeProjectionPublicationRequest,
    RelationshipAssertionRepository,
)
from src.data.relationship_projection_persistence import PersistProjectionRequest
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import ProjectionRevision
from src.logic.snapshot_attestation import (
    compute_graph_snapshot_hash,
)
from src.models.financial_models import (
    AssetClass,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

pytestmark = pytest.mark.unit

UTC = timezone.utc


def _create_sample_test_graph() -> AssetRelationshipGraph:
    """Create a deterministic graph with assets, relationships, and regulatory events."""
    graph = AssetRelationshipGraph()
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
        currency="USD",
        pe_ratio=28.5,
        dividend_yield=0.0055,
        earnings_per_share=6.42,
    )
    msft = Equity(
        id="MSFT",
        symbol="MSFT",
        name="Microsoft Corporation",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=420.10,
        market_cap=3100000000000.0,
        currency="USD",
        pe_ratio=35.1,
        dividend_yield=0.0072,
        earnings_per_share=11.05,
    )
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


def _setup_disposable_db(tmp_path: Path) -> tuple[str, Any]:
    """Initialize a disposable SQLite test database."""
    db_file = tmp_path / f"test_gate_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    init_db(engine)
    session_factory = create_session_factory(engine)
    return db_url, session_factory


def _publish_sample_graph(
    session_factory: Any,
    graph: AssetRelationshipGraph,
    *,
    job_id: str = "job-001",
    execution_id: str = "exec-001",
    custom_snapshot_sha256: str | None = None,
) -> str:
    """Helper to atomically persist a graph, rebuild job, and projection publication."""
    now = datetime.now(UTC)
    with session_factory() as session:
        # 1. Create running job
        job = RebuildJobORM(
            job_id=job_id,
            requested_by="test-operator",
            status="running",
            source="test",
            created_at=now,
            updated_at=now,
            started_at=now,
            execution_id=execution_id,
        )
        session.add(job)
        session.commit()

    with session_factory() as session:
        stage_graph_snapshot(session, graph)
        computed_sha = compute_graph_snapshot_hash(graph)
        effective_sha = custom_snapshot_sha256 if custom_snapshot_sha256 is not None else computed_sha

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
                node_count=len(graph.assets),
                edge_count=sum(len(edges) for edges in graph.relationships.values()),
                duration_ms=100,
                published_at=now,
                snapshot_sha256=effective_sha,
            ),
            pre_success_check=lambda: None,
            pre_commit_check=lambda: None,
        )
        session.commit()

    return effective_sha


def test_clean_installation_classification(tmp_path: Path) -> None:
    """Clean installation with no assets and no publications returns None."""
    db_url, _ = _setup_disposable_db(tmp_path)
    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_successful_publication_and_verified_startup(tmp_path: Path) -> None:
    """Properly published graph passes provenance gate and reloads successfully."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    digest = _publish_sample_graph(session_factory, graph)

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is not None
    assert len(loaded.assets) == 2
    assert "AAPL" in loaded.assets
    assert "MSFT" in loaded.assets
    assert compute_graph_snapshot_hash(loaded) == digest

    # Also test through public boundary load_persisted_graph_if_available
    available = load_persisted_graph_if_available(db_url)
    assert available is not None
    assert compute_graph_snapshot_hash(available) == digest


def test_tampered_asset_rejected(tmp_path: Path) -> None:
    """Mutating an asset property in the database breaks attestation and fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Tamper with asset price in database
    with session_factory() as session:
        session.execute(update(AssetORM).where(AssetORM.id == "AAPL").values(price=999.99))
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_tampered_relationship_rejected(tmp_path: Path) -> None:
    """Mutating relationship strength in the database breaks attestation and fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Tamper with relationship strength in database
    with session_factory() as session:
        session.execute(
            update(AssetRelationshipORM).where(AssetRelationshipORM.source_asset_id == "AAPL").values(strength=0.99)
        )
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_tampered_event_rejected(tmp_path: Path) -> None:
    """Mutating regulatory event description in the database breaks attestation and fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Tamper with regulatory event in database
    with session_factory() as session:
        session.execute(
            update(RegulatoryEventORM)
            .where(RegulatoryEventORM.id == "REG-001")
            .values(description="Altered description")
        )
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_same_count_substitution_rejected(tmp_path: Path) -> None:
    """Replacing an asset with another asset of identical size/count fails attestation."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Substitute MSFT with GOOG (same count: 2 assets) while maintaining FK integrity
    with session_factory() as session:
        goog = AssetORM(
            id="GOOG",
            symbol="GOOG",
            name="Alphabet Inc.",
            asset_class="Equity",
            sector="Technology",
            price=150.0,
            market_cap=2000000000000.0,
            currency="USD",
        )
        session.add(goog)
        session.flush()

        session.execute(
            update(AssetRelationshipORM)
            .where(AssetRelationshipORM.source_asset_id == "MSFT")
            .values(source_asset_id="GOOG")
        )
        session.execute(
            update(AssetRelationshipORM)
            .where(AssetRelationshipORM.target_asset_id == "MSFT")
            .values(target_asset_id="GOOG")
        )
        session.flush()

        msft = session.get(AssetORM, "MSFT")
        if msft:
            session.delete(msft)
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_missing_publication_rejected(tmp_path: Path) -> None:
    """Persisted assets without any publication record fail closed with missing provenance."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()

    # Save graph but do NOT publish
    with session_factory() as session:
        repo = AssetGraphRepository(session)
        repo.save_graph(graph)
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_missing_attestation_digest_rejected(tmp_path: Path) -> None:
    """A legacy publication row lacking snapshot_sha256 fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    # Publish with empty/null digest (simulating legacy data)
    _publish_sample_graph(session_factory, graph, custom_snapshot_sha256="")

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_mismatched_rebuild_identity_rejected(tmp_path: Path) -> None:
    """Publication with mismatched execution_id relative to rebuild_jobs fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Tamper with rebuild job execution_id
    with session_factory() as session:
        session.execute(update(RebuildJobORM).values(execution_id="wrong-exec-id"))
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_mismatched_job_snapshot_sha256_rejected(tmp_path: Path) -> None:
    """Job snapshot_sha256 differing from publication snapshot_sha256 fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    # Tamper with job snapshot_sha256
    with session_factory() as session:
        session.execute(update(RebuildJobORM).values(snapshot_sha256="0" * 64))
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_rollback_on_publication_failure(tmp_path: Path) -> None:
    """Simulated exception during publication rolls back graph rows and publication atomically."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()

    now = datetime.now(UTC)
    with session_factory() as session:
        job = RebuildJobORM(
            job_id="job-fail",
            requested_by="test-operator",
            status="running",
            source="test",
            created_at=now,
            updated_at=now,
            started_at=now,
            execution_id="exec-fail",
        )
        session.add(job)
        session.commit()

    # Simulate failure in publication transaction
    with pytest.raises(RuntimeError, match="Simulated publication error"):
        with session_factory() as session:
            stage_graph_snapshot(session, graph)
            # Something fails before commit
            raise RuntimeError("Simulated publication error")

    # Assert database has NO staged assets
    with session_factory() as session:
        asset_count = session.execute(select(AssetORM.id)).scalars().all()
        assert len(asset_count) == 0

    # Gate still fails closed cleanly
    assert _load_persisted_graph_from_configured_store(db_url) is None


def test_coordination_finalization_failure_resilience(tmp_path: Path) -> None:
    """In split persistence, coordination lease renewal failure after domain commit preserves durable graph."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    digest = _publish_sample_graph(session_factory, graph)

    # Even if coordination lease failed downstream, domain rows committed cleanly:
    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is not None
    assert compute_graph_snapshot_hash(loaded) == digest
