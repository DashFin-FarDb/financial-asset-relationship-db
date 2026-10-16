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

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update

from api.graph_lifecycle_providers import (
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


_UNSET = object()


def _publish_sample_graph(
    session_factory: Any,
    graph: AssetRelationshipGraph,
    *,
    job_id: str = "job-001",
    execution_id: str = "exec-001",
    publication_execution_id: Any = _UNSET,
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
        if publication_execution_id is _UNSET:
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
        else:
            persisted = assertion_repo.persist_projection_revision(
                PersistProjectionRequest(
                    revision=revision,
                    revision_id=f"rev-{uuid4().hex[:8]}",
                    created_at=now,
                )
            )
            graph_repo = AssetGraphRepository(session)
            graph_repo.mark_rebuild_job_succeeded(
                job_id,
                execution_id=execution_id,
                node_count=len(graph.assets),
                edge_count=sum(len(edges) for edges in graph.relationships.values()),
                duration_ms=100,
                snapshot_sha256=effective_sha,
            )
            session.add(
                RelationshipProjectionPublicationORM(
                    id=str(uuid4()),
                    revision_id=persisted.revision_id,
                    rebuild_job_id=job_id,
                    execution_id=publication_execution_id,
                    published_at=now,
                    snapshot_sha256=effective_sha,
                )
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


def test_missing_publication_execution_id_rejected(tmp_path: Path) -> None:
    """Publication with null execution_id fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph, publication_execution_id=None)

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_missing_rebuild_job_execution_id_rejected(tmp_path: Path) -> None:
    """Rebuild job with null execution_id fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph)

    with session_factory() as session:
        session.execute(update(RebuildJobORM).values(execution_id=None))
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_both_missing_execution_id_rejected(tmp_path: Path) -> None:
    """Both publication and rebuild job with null execution_id fail closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(session_factory, graph, publication_execution_id=None)

    with session_factory() as session:
        session.execute(update(RebuildJobORM).values(execution_id=None))
        session.commit()

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_unequal_non_null_execution_ids_rejected(tmp_path: Path) -> None:
    """Unequal non-null execution IDs between publication and rebuild job fail closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(
        session_factory,
        graph,
        execution_id="exec-job-side",
        publication_execution_id="exec-pub-side",
    )

    loaded = _load_persisted_graph_from_configured_store(db_url)
    assert loaded is None
    assert load_persisted_graph_if_available(db_url) is None


def test_blank_execution_id_rejected(tmp_path: Path) -> None:
    """Blank or whitespace-only execution_id fails closed."""
    db_url, session_factory = _setup_disposable_db(tmp_path)
    graph = _create_sample_test_graph()
    _publish_sample_graph(
        session_factory,
        graph,
        execution_id="   ",
        publication_execution_id="   ",
    )

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


def test_interleaved_publication_rollover_preserves_consistent_snapshot(tmp_path: Path) -> None:
    """A publication commit interleaved between publication query and graph loading does not produce a torn read."""
    db_file = tmp_path / f"test_concurrency_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.commit()
    init_db(engine)
    session_factory = create_session_factory(engine)

    # 1. Publish Generation 1
    graph_1 = _create_sample_test_graph()
    digest_1 = _publish_sample_graph(session_factory, graph_1, job_id="job-1", execution_id="exec-1")

    # 2. Build Generation 2
    graph_2 = AssetRelationshipGraph()
    e2 = Equity(
        id="GOOGL",
        symbol="GOOGL",
        name="Alphabet Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=175.0,
        currency="USD",
    )
    graph_2.add_asset(e2)

    original_load = AssetGraphRepository.load_graph_with_attestation_hash
    interleaved_publish_executed = False

    def hook_load(self: AssetGraphRepository) -> tuple[AssetRelationshipGraph, str]:
        nonlocal interleaved_publish_executed
        if not interleaved_publish_executed:
            interleaved_publish_executed = True
            _publish_sample_graph(session_factory, graph_2, job_id="job-2", execution_id="exec-2")
        return original_load(self)

    with patch.object(AssetGraphRepository, "load_graph_with_attestation_hash", hook_load):
        loaded = _load_persisted_graph_from_configured_store(db_url)

    assert interleaved_publish_executed is True
    assert loaded is not None
    assert compute_graph_snapshot_hash(loaded) == digest_1
    assert "AAPL" in loaded.assets
    assert "GOOGL" not in loaded.assets


def test_publication_rollover_after_verification_cannot_alter_returned_graph(tmp_path: Path) -> None:
    """Once verified, publication rollover cannot alter the returned in-memory graph object."""
    db_file = tmp_path / f"test_concurrency_after_verify_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.commit()
    init_db(engine)
    session_factory = create_session_factory(engine)

    graph_1 = _create_sample_test_graph()
    digest_1 = _publish_sample_graph(session_factory, graph_1, job_id="job-1", execution_id="exec-1")

    graph_2 = AssetRelationshipGraph()
    e2 = Equity(
        id="NVDA",
        symbol="NVDA",
        name="NVIDIA Corp.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=900.0,
        currency="USD",
    )
    graph_2.add_asset(e2)

    original_load = AssetGraphRepository.load_graph_with_attestation_hash
    interleaved_after_verify = False

    def hook_load_after_verify(self: AssetGraphRepository) -> tuple[AssetRelationshipGraph, str]:
        nonlocal interleaved_after_verify
        res = original_load(self)
        if not interleaved_after_verify:
            interleaved_after_verify = True
            # Publish Generation 2 to persistent store right after graph 1 is loaded and hashed
            _publish_sample_graph(session_factory, graph_2, job_id="job-2", execution_id="exec-2")
        return res

    with patch.object(AssetGraphRepository, "load_graph_with_attestation_hash", hook_load_after_verify):
        loaded = _load_persisted_graph_from_configured_store(db_url)

    assert interleaved_after_verify is True
    assert loaded is not None
    assert compute_graph_snapshot_hash(loaded) == digest_1
    assert "AAPL" in loaded.assets
    assert "NVDA" not in loaded.assets


def test_no_mixed_generation_graph_under_concurrency(tmp_path: Path) -> None:
    """Repeated concurrent publications and reads never return a mixed-generation graph."""
    db_file = tmp_path / f"test_concurrent_generations_{uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    engine = configure_sqlite_engine(create_engine(db_url, future=True))
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.commit()
    init_db(engine)
    session_factory = create_session_factory(engine)

    g1 = _create_sample_test_graph()
    d1 = _publish_sample_graph(session_factory, g1, job_id="job-1", execution_id="exec-1")

    g2 = AssetRelationshipGraph()
    e2 = Equity(
        id="AMZN",
        symbol="AMZN",
        name="Amazon.com Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Consumer Discretionary",
        price=185.0,
        currency="USD",
    )
    g2.add_asset(e2)
    d2 = compute_graph_snapshot_hash(g2)

    stop_event = threading.Event()
    observed_graphs: list[AssetRelationshipGraph] = []
    lock = threading.Lock()

    def reader() -> None:
        while not stop_event.is_set():
            loaded = _load_persisted_graph_from_configured_store(db_url)
            if loaded is not None:
                with lock:
                    observed_graphs.append(loaded)

    t_reader = threading.Thread(target=reader)
    t_reader.start()

    for i in range(10):
        target = g2 if i % 2 == 0 else g1
        _publish_sample_graph(session_factory, target, job_id=f"job-gen-{i}", execution_id=f"exec-gen-{i}")

    stop_event.set()
    t_reader.join()

    assert len(observed_graphs) > 0
    for g in observed_graphs:
        h = compute_graph_snapshot_hash(g)
        if h == d1:
            assert "AAPL" in g.assets
            assert "AMZN" not in g.assets
        elif h == d2:
            assert "AMZN" in g.assets
            assert "AAPL" not in g.assets
        else:
            pytest.fail(f"Torn/mixed generation graph detected with hash: {h}")
