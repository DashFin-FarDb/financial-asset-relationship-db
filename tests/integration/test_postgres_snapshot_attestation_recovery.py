"""PostgreSQL 15/16 integration test suite for snapshot attestation recovery.

Validates the complete fail-closed attestation gate and authorized rebuild recovery
lifecycle against real PostgreSQL instances using the approved disposable cluster
harness and Supabase graph ledger.

Scenarios verified:
1. Immutability trigger enforcement & transaction rollback
2. Tampered asset row detection, rejection & recovery
3. Tampered relationship row detection, rejection & recovery
4. Tampered regulatory event detection, rejection & recovery
5. Corrupted publication digest rejection & recovery
6. Mismatched execution_id rejection & recovery
7. Missing publication provenance (legacy state) rejection & recovery
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest
from psycopg2 import sql
from sqlalchemy import text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from api.graph_lifecycle_providers import (
    _load_persisted_graph_from_configured_store,
    load_persisted_graph_if_available,
    stage_graph_snapshot,
)
from scripts.postgresql_ledger import (
    LedgerManifest,
    PlannedTarget,
    apply_profile_to_database,
    assert_profile_write_allowed,
    load_and_validate_manifest,
)
from src.data.db_models import (
    AssetORM,
    AssetRelationshipORM,
    RebuildJobORM,
    RegulatoryEventORM,
)
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
    compute_repository_snapshot_hash,
)
from src.models.financial_models import (
    AssetClass,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)
from tests.integration.postgresql_disposable_cluster import (
    ContainerCliRunner,
    attested_connection,
    connect_owned_attested,
    create_attested_engine,
    execute_capability_bootstrap,
    record_created_role,
)

pytestmark = pytest.mark.integration
# pylint: disable=redefined-outer-name

_ENABLE_ENV = "FARDB_EPHEMERAL_POSTGRES_LEDGER_TESTS"
_URL_ENV = "FARDB_EPHEMERAL_POSTGRES_URL"
UTC = timezone.utc


def _ephemeral_postgres_url() -> str:
    """Return the verified disposable PostgreSQL service URL or skip offline runs."""
    if os.environ.get(_ENABLE_ENV) != "1":
        pytest.skip(f"Set {_ENABLE_ENV}=1 to run disposable PostgreSQL ledger proofs")
    value = os.environ.get(_URL_ENV)
    if not value:
        pytest.fail(f"{_URL_ENV} is required when {_ENABLE_ENV}=1")
    assert value is not None
    target = PlannedTarget(
        logical_targets=("graph",),
        profile="graph",
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=value,
    )
    assert_profile_write_allowed(target)
    parsed = urlsplit(value)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "disable"
    normalized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    assert_profile_write_allowed(replace(target, database_url=normalized))
    with attested_connection(normalized):
        pass
    return normalized


def _database_url(base_url: str, database_name: str) -> str:
    """Select a disposable database name preserving the base authority."""
    parsed = urlsplit(base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))


def _bootstrap_roles_and_create_database(base_url: str, database_name: str) -> None:
    """Create capability roles and one empty disposable database."""
    connection = connect_owned_attested(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (["fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination"],),
            )
            preexisting_capabilities = {row[0] for row in cursor.fetchall()}
            execute_capability_bootstrap(cursor)
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (["fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination"],),
            )
            for (name,) in cursor.fetchall():
                if name not in preexisting_capabilities:
                    record_created_role(connection, name, canonical_test_role=True)
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        connection.close()


def _drop_database(base_url: str, database_name: str) -> None:
    """Terminate connections and drop one generated disposable database."""
    connection = connect_owned_attested(base_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        connection.close()


@pytest.fixture
def disposable_graph_database() -> Iterator[tuple[str, Engine, sessionmaker[Session]]]:
    """Provide an isolated disposable PostgreSQL database initialized via the graph ledger."""
    base_url = _ephemeral_postgres_url()
    database_name = f"attest_rec_{uuid4().hex[:12]}"
    target_url = _database_url(base_url, database_name)
    manifest: LedgerManifest = load_and_validate_manifest()
    target = PlannedTarget(
        logical_targets=("graph",),
        profile="graph",
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=target_url,
    )

    _bootstrap_roles_and_create_database(base_url, database_name)
    with ContainerCliRunner(target_url) as runner:
        apply_profile_to_database(target, manifest, runner=runner)

    engine = create_attested_engine(target_url, future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

    try:
        yield target_url, engine, session_factory
    finally:
        engine.dispose()
        _drop_database(base_url, database_name)


def _create_deterministic_graph(label: str = "V1") -> AssetRelationshipGraph:
    """Construct a deterministic test graph with distinct assets, relationships and events."""
    graph = AssetRelationshipGraph()
    eq1 = Equity(
        id=f"ASSET_{label}_1",
        symbol=f"A{label}1",
        name=f"Asset {label} 1",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=150.0,
        market_cap=1_000_000_000.0,
        currency="USD",
    )
    eq2 = Equity(
        id=f"ASSET_{label}_2",
        symbol=f"A{label}2",
        name=f"Asset {label} 2",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=250.0,
        market_cap=2_000_000_000.0,
        currency="USD",
    )
    graph.add_asset(eq1)
    graph.add_asset(eq2)
    graph.add_relationship(f"ASSET_{label}_1", f"ASSET_{label}_2", "correlates_with", 0.75)
    graph.add_regulatory_event(
        RegulatoryEvent(
            id=f"REG_{label}_1",
            asset_id=f"ASSET_{label}_1",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2026-01-01",
            description=f"Regulatory filing {label}",
            impact_score=0.1,
            related_assets=[f"ASSET_{label}_2"],
        )
    )
    return graph


def _publish_attested_graph(
    session_factory: sessionmaker[Session],
    graph: AssetRelationshipGraph,
    *,
    job_id: str = "job-001",
    execution_id: str = "exec-001",
    custom_snapshot_sha256: str | None = None,
) -> str:
    """Persist and publish an attested graph snapshot through production assertion boundaries."""
    now = datetime.now(UTC)
    with session_factory() as session:
        job = RebuildJobORM(
            job_id=job_id,
            requested_by="rebuild-operator",
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
        session.flush()
        computed_sha = compute_repository_snapshot_hash(AssetGraphRepository(session))
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
                duration_ms=50,
                published_at=now,
                snapshot_sha256=effective_sha,
            ),
            pre_success_check=lambda: None,
            pre_commit_check=lambda: None,
        )
        session.commit()

    return effective_sha


def _assert_persisted_graph_matches_digest(target_url: str, expected_digest: str) -> AssetRelationshipGraph:
    """Assert that the persisted graph can be loaded and its hash matches the expected digest."""
    loaded = _load_persisted_graph_from_configured_store(target_url)
    assert loaded is not None
    assert compute_graph_snapshot_hash(loaded) == expected_digest
    return loaded


def _publish_and_verify_baseline(
    session_factory: sessionmaker[Session],
    target_url: str,
    label: str,
    job_id: str,
    execution_id: str,
) -> tuple[AssetRelationshipGraph, str]:
    """Publish a baseline graph and verify that initial persistence loads and attestation match."""
    graph = _create_deterministic_graph(label)
    digest = _publish_attested_graph(session_factory, graph, job_id=job_id, execution_id=execution_id)
    _assert_persisted_graph_matches_digest(target_url, digest)
    return graph, digest


def _assert_fail_closed_startup(target_url: str) -> None:
    """Assert that store startup fails closed when attestation or provenance is compromised."""
    assert _load_persisted_graph_from_configured_store(target_url) is None
    assert load_persisted_graph_if_available(target_url) is None


def _rebuild_and_verify_recovered_graph(
    session_factory: sessionmaker[Session],
    target_url: str,
    *,
    label: str,
    job_id: str,
    execution_id: str,
    expected_new_asset_id: str,
    excluded_prior_asset_id: str | None = None,
) -> tuple[AssetRelationshipGraph, str]:
    """Execute an authorized rebuild and verify that the recovered graph loads cleanly."""
    _assert_fail_closed_startup(target_url)

    graph_v2 = _create_deterministic_graph(label)
    v2_digest = _publish_attested_graph(
        session_factory,
        graph_v2,
        job_id=job_id,
        execution_id=execution_id,
    )

    loaded_v2 = _assert_persisted_graph_matches_digest(target_url, v2_digest)
    assert expected_new_asset_id in loaded_v2.assets
    if excluded_prior_asset_id is not None:
        assert excluded_prior_asset_id not in loaded_v2.assets

    return graph_v2, v2_digest


def test_postgres_publication_immutability_and_rollback(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """PostgreSQL triggers must enforce GRAC v1 immutability and roll back mutations cleanly."""
    target_url, _engine, session_factory = disposable_graph_database
    _graph_v1, v1_digest = _publish_and_verify_baseline(
        session_factory, target_url, "V1", job_id="job-imm-001", execution_id="exec-imm-001"
    )

    # 1. Attempt unauthorized direct UPDATE on publications table
    update_stmt = update(RelationshipProjectionPublicationORM).values(
        snapshot_sha256="deadbeef" * 8,
    )
    with session_factory() as session:
        with pytest.raises(IntegrityError) as exc_info:
            session.execute(update_stmt)
        assert "GRAC v1 immutability: UPDATE forbidden on relationship_projection_publications" in str(exc_info.value)
        session.rollback()

    # 2. Verify failed UPDATE rolled back and original publication remains verified
    _assert_persisted_graph_matches_digest(target_url, v1_digest)

    # 3. Attempt unauthorized direct DELETE on publications table
    delete_stmt = text("DELETE FROM public.relationship_projection_publications")
    with session_factory() as session:
        with pytest.raises(IntegrityError) as exc_info:
            session.execute(delete_stmt)
        assert "GRAC v1 immutability: DELETE forbidden on relationship_projection_publications" in str(exc_info.value)
        session.rollback()

    # 4. Verify failed DELETE rolled back and original publication remains verified
    _assert_persisted_graph_matches_digest(target_url, v1_digest)


def test_postgres_recovery_tampered_asset(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """Mutating asset attributes in PostgreSQL breaks attestation and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    _publish_and_verify_baseline(session_factory, target_url, "V1", job_id="job-ast-001", execution_id="exec-ast-001")

    # Out-of-band mutation: alter asset price in database
    with session_factory() as session:
        session.execute(update(AssetORM).where(AssetORM.id == "ASSET_V1_1").values(price=999999.0))
        session.commit()

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_AST_RECOVERED",
        job_id="job-ast-002",
        execution_id="exec-ast-002",
        expected_new_asset_id="ASSET_V2_AST_RECOVERED_1",
        excluded_prior_asset_id="ASSET_V1_1",
    )


def test_postgres_recovery_tampered_relationship(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """Mutating edge strength in PostgreSQL breaks attestation and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    _publish_and_verify_baseline(session_factory, target_url, "V1", job_id="job-rel-001", execution_id="exec-rel-001")

    # Out-of-band mutation: alter relationship strength
    with session_factory() as session:
        session.execute(
            update(AssetRelationshipORM)
            .where(AssetRelationshipORM.source_asset_id == "ASSET_V1_1")
            .values(strength=0.9999)
        )
        session.commit()

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_REL_RECOVERED",
        job_id="job-rel-002",
        execution_id="exec-rel-002",
        expected_new_asset_id="ASSET_V2_REL_RECOVERED_1",
    )


def test_postgres_recovery_tampered_regulatory_event(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """Mutating event description in PostgreSQL breaks attestation and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    _publish_and_verify_baseline(session_factory, target_url, "V1", job_id="job-reg-001", execution_id="exec-reg-001")

    # Out-of-band mutation: alter event description
    with session_factory() as session:
        session.execute(
            update(RegulatoryEventORM)
            .where(RegulatoryEventORM.id == "REG_V1_1")
            .values(description="Illicitly altered regulatory filing")
        )
        session.commit()

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_REG_RECOVERED",
        job_id="job-reg-002",
        execution_id="exec-reg-002",
        expected_new_asset_id="ASSET_V2_REG_RECOVERED_1",
    )


def test_postgres_recovery_corrupted_publication_digest(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """A publication with mismatched snapshot_sha256 fails closed and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    graph_v1 = _create_deterministic_graph("V1")

    # Initial publication with deliberately mismatched digest
    _publish_attested_graph(
        session_factory,
        graph_v1,
        job_id="job-dig-001",
        execution_id="exec-dig-001",
        custom_snapshot_sha256="bad" * 21 + "a",
    )

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_DIG_RECOVERED",
        job_id="job-dig-002",
        execution_id="exec-dig-002",
        expected_new_asset_id="ASSET_V2_DIG_RECOVERED_1",
    )


def test_postgres_recovery_mismatched_execution_identity(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """A publication with mismatched execution_id fails closed and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    graph_v1 = _create_deterministic_graph("V1")
    now = datetime.now(UTC)

    # Setup mismatched execution identity
    with session_factory() as session:
        job = RebuildJobORM(
            job_id="job-mid-001",
            requested_by="rebuild-operator",
            status="running",
            source="test",
            created_at=now,
            updated_at=now,
            started_at=now,
            execution_id="exec-mid-001-job",
        )
        session.add(job)
        session.commit()

    with session_factory() as session:
        stage_graph_snapshot(session, graph_v1)
        session.flush()
        sha = compute_repository_snapshot_hash(AssetGraphRepository(session))
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
        persisted = assertion_repo.persist_projection_revision(
            PersistProjectionRequest(
                revision=revision,
                revision_id=f"rev-{uuid4().hex[:8]}",
                created_at=now,
            )
        )
        session.add(
            RelationshipProjectionPublicationORM(
                id=str(uuid4()),
                revision_id=persisted.revision_id,
                rebuild_job_id="job-mid-001",
                execution_id="exec-mid-001-STALE-ZOMBIE-EXECUTOR",
                published_at=now,
                snapshot_sha256=sha,
            )
        )
        session.commit()

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_MID_RECOVERED",
        job_id="job-mid-002",
        execution_id="exec-mid-002-AUTHORIZED",
        expected_new_asset_id="ASSET_V2_MID_RECOVERED_1",
    )


def test_postgres_recovery_missing_publication_provenance(
    disposable_graph_database: tuple[str, Engine, sessionmaker[Session]],
) -> None:
    """A database with assets but no publication record fails closed and recovers via rebuild."""
    target_url, _engine, session_factory = disposable_graph_database
    graph_v1 = _create_deterministic_graph("V1")

    # Populate asset rows without any publication (legacy un-attested state)
    with session_factory() as session:
        stage_graph_snapshot(session, graph_v1)
        session.commit()

    _rebuild_and_verify_recovered_graph(
        session_factory,
        target_url,
        label="V2_LEG_RECOVERED",
        job_id="job-leg-002",
        execution_id="exec-leg-002",
        expected_new_asset_id="ASSET_V2_LEG_RECOVERED_1",
    )
