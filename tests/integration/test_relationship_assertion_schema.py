"""Integration tests for GRAC v1 assertion schema bootstrap and immutability."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.data.base import Base
from src.data.database import init_db
from src.data.db_models import AssetORM, RebuildJobORM
from src.data.relationship_assertion_db_models import (
    GRAC_TABLE_NAMES,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
)
from src.data.relationship_assertion_schema import (
    ensure_relationship_assertion_schema,
    list_immutability_trigger_names,
)
from tests.conftest import enable_sqlite_foreign_keys

UTC = timezone.utc
DIGEST = "c" * 64

LEGACY_TABLES = (
    "assets",
    "asset_relationships",
    "regulatory_events",
    "regulatory_event_assets",
    "rebuild_jobs",
    "distributed_locks",
)

EXPECTED_CHECK_NAMES = {
    "relationship_evidence": {
        "ck_relationship_evidence_visibility",
        "ck_relationship_evidence_sha256_hex",
    },
    "relationship_assertions": {
        "ck_relationship_assertions_confidence_status",
        "ck_relationship_assertions_confidence_bp",
        "ck_relationship_assertions_confidence_assessed",
    },
    "relationship_assertion_evidence": {"ck_relationship_assertion_evidence_polarity"},
    "relationship_assertion_events": {
        "ck_relationship_assertion_events_from_state",
        "ck_relationship_assertion_events_to_state",
        "ck_relationship_assertion_events_sequence",
    },
    "relationship_projection_revisions": {
        "ck_relationship_projection_revisions_edge_set_hash_hex",
        "ck_relationship_projection_revisions_projection_hash_hex",
    },
    "relationship_projection_edges": {
        "ck_relationship_projection_edges_direction",
        "ck_relationship_projection_edges_strength",
    },
}

EXPECTED_INDEX_NAMES = {
    "relationship_evidence": {
        "ix_relationship_evidence_content_sha256",
        "ix_relationship_evidence_recorded_at",
    },
    "relationship_assertions": {
        "ix_relationship_assertions_predicate_subject",
        "ix_relationship_assertions_recorded_at",
        "ix_relationship_assertions_effective_from",
    },
    "relationship_assertion_evidence": {
        "ix_relationship_assertion_evidence_assertion_id",
        "ix_relationship_assertion_evidence_evidence_id",
        "ix_relationship_assertion_evidence_recorded_at",
        "uq_relationship_assertion_evidence_link",
    },
    "relationship_assertion_events": {
        "ix_relationship_assertion_events_assertion_id",
        "ix_relationship_assertion_events_recorded_at",
        "uq_relationship_assertion_events_sequence",
    },
    "relationship_projection_revisions": {
        "ix_relationship_projection_revisions_purpose",
        "ix_relationship_projection_revisions_created_at",
        "ix_relationship_projection_revisions_effective_known",
    },
    "relationship_projection_edges": {
        "ix_relationship_projection_edges_revision_id",
        "ix_relationship_projection_edges_assertion_id",
        "ix_relationship_projection_edges_source_target",
    },
    "relationship_projection_publications": {
        "ix_relationship_projection_publications_revision_id",
        "ix_relationship_projection_publications_rebuild_job_id",
        "ix_relationship_projection_publications_published_at",
        "uq_relationship_projection_publications_rev_job",
    },
}


def _postgres_url() -> str | None:
    """Return a PostgreSQL URL when CI/local opt-in provides one."""
    url = os.getenv("ASSET_GRAPH_DATABASE_URL") or os.getenv("GRAC_SCHEMA_DATABASE_URL")
    if url and url.startswith("postgresql"):
        return url
    return None


@pytest.fixture(params=["sqlite", "postgresql"])
def schema_engine(request, tmp_path) -> Engine:
    """Provide SQLite always; PostgreSQL when an ephemeral URL is configured."""
    dialect = request.param
    if dialect == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'grac_schema.db'}")
        enable_sqlite_foreign_keys(engine)
        yield engine
        engine.dispose()
        return

    pg_url = _postgres_url()
    if not pg_url:
        pytest.skip("PostgreSQL URL not set (ASSET_GRAPH_DATABASE_URL / GRAC_SCHEMA_DATABASE_URL)")
    pytest.importorskip("psycopg2")
    engine = create_engine(pg_url, future=True)
    # Isolate CI runs by dropping GRAC + legacy tables owned by these tests.
    Base.metadata.drop_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _check_names(engine: Engine, table: str) -> set[str]:
    return {item["name"] for item in inspect(engine).get_check_constraints(table)}


def _index_names(engine: Engine, table: str) -> set[str]:
    names = {item["name"] for item in inspect(engine).get_indexes(table) if item.get("name")}
    # UniqueConstraints may appear as unique indexes depending on dialect.
    for uk in inspect(engine).get_unique_constraints(table):
        if uk.get("name"):
            names.add(uk["name"])
    return names


def _fk_pairs(engine: Engine, table: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for fk in inspect(engine).get_foreign_keys(table):
        referred = fk.get("referred_table")
        for local_col, remote_col in zip(
            fk.get("constrained_columns") or [],
            fk.get("referred_columns") or [],
            strict=True,
        ):
            pairs.add((f"{table}.{local_col}", f"{referred}.{remote_col}"))
    return pairs


@pytest.mark.integration
class TestRelationshipAssertionSchemaBootstrap:
    """Fresh create, upgrade, and idempotent re-init."""

    @staticmethod
    def test_fresh_creation(schema_engine: Engine):
        """Fresh init_db creates all seven GRAC tables plus legacy tables."""
        init_db(schema_engine)
        names = _table_names(schema_engine)
        assert set(GRAC_TABLE_NAMES).issubset(names)
        assert set(LEGACY_TABLES).issubset(names)

    @staticmethod
    def test_upgrade_over_existing_legacy_database(schema_engine: Engine):
        """init_db adds GRAC tables without removing pre-existing legacy data."""
        # Create only legacy ORM tables first (simulate pre-GRAC database).
        for table_name in LEGACY_TABLES:
            Base.metadata.tables[table_name].create(schema_engine, checkfirst=True)

        with schema_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO assets (id, symbol, name, asset_class, sector, price, currency) "
                    "VALUES ('LEGACY', 'LEG', 'Legacy', 'equity', 'Tech', 1.0, 'USD')"
                )
            )

        assert "relationship_assertions" not in _table_names(schema_engine)

        init_db(schema_engine)

        names = _table_names(schema_engine)
        assert set(GRAC_TABLE_NAMES).issubset(names)
        assert set(LEGACY_TABLES).issubset(names)
        with schema_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM assets WHERE id = 'LEGACY'")).scalar_one()
        assert count == 1

    @staticmethod
    def test_repeated_initialization_is_idempotent(schema_engine: Engine):
        """Calling init_db twice does not error and keeps tables/triggers."""
        init_db(schema_engine)
        init_db(schema_engine)
        ensure_relationship_assertion_schema(schema_engine)
        assert set(GRAC_TABLE_NAMES).issubset(_table_names(schema_engine))


@pytest.mark.integration
class TestRelationshipAssertionSchemaParity:
    """FK / CHECK / index presence (SQLite and PostgreSQL when available)."""

    @staticmethod
    def test_check_and_index_parity(schema_engine: Engine):
        """Named checks and indexes exist for each GRAC table."""
        init_db(schema_engine)
        for table, expected in EXPECTED_CHECK_NAMES.items():
            actual = _check_names(schema_engine, table)
            missing = expected - actual
            assert not missing, f"{table} missing checks: {missing} (have {actual})"

        for table, expected in EXPECTED_INDEX_NAMES.items():
            actual = _index_names(schema_engine, table)
            missing = expected - actual
            assert not missing, f"{table} missing indexes: {missing} (have {actual})"

    @staticmethod
    def test_foreign_key_targets(schema_engine: Engine):
        """Core foreign keys point at the expected parent tables."""
        init_db(schema_engine)
        expected = {
            ("relationship_assertion_evidence.assertion_id", "relationship_assertions.id"),
            ("relationship_assertion_evidence.evidence_id", "relationship_evidence.id"),
            ("relationship_assertion_events.assertion_id", "relationship_assertions.id"),
            ("relationship_projection_edges.revision_id", "relationship_projection_revisions.id"),
            ("relationship_projection_edges.assertion_id", "relationship_assertions.id"),
            ("relationship_projection_publications.revision_id", "relationship_projection_revisions.id"),
            ("relationship_projection_publications.rebuild_job_id", "rebuild_jobs.job_id"),
        }
        actual: set[tuple[str, str]] = set()
        for table in GRAC_TABLE_NAMES:
            actual |= _fk_pairs(schema_engine, table)
        missing = expected - actual
        assert not missing, f"missing FKs: {missing}"


@pytest.mark.integration
class TestRelationshipAssertionImmutability:
    """UPDATE/DELETE must be rejected on guarded tables."""

    @staticmethod
    def test_update_and_delete_rejected(schema_engine: Engine):
        """Immutability triggers reject mutation on source-of-truth tables."""
        init_db(schema_engine)
        now = datetime.now(tz=UTC)
        with schema_engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO relationship_evidence (
                        id, source_ref, content_sha256, media_type, visibility, custody_id, recorded_at
                    ) VALUES (
                        'ev-imm', 'ref', :digest, 'text/plain', 'internal', 'custody', :now
                    )
                    """),
                {"digest": DIGEST, "now": now},
            )
            conn.execute(
                text("""
                    INSERT INTO relationship_assertions (
                        id, predicate_id, subject_id, object_id, method_id, proposition,
                        confidence_status, effective_from, recorded_at
                    ) VALUES (
                        'as-imm', 'financial.bond.issuer_reference@1', 'AAPL_BOND_2030', 'AAPL',
                        'bond.issuer_id.resolution@1', 'prop', 'not_assessed', :now, :now
                    )
                    """),
                {"now": now},
            )

        with pytest.raises((IntegrityError, DBAPIError)):
            with schema_engine.begin() as conn:
                conn.execute(
                    text("UPDATE relationship_evidence SET media_type = 'application/json' WHERE id = 'ev-imm'")
                )

        with pytest.raises((IntegrityError, DBAPIError)):
            with schema_engine.begin() as conn:
                conn.execute(text("DELETE FROM relationship_assertions WHERE id = 'as-imm'"))

        # Rows remain after failed mutations.
        with schema_engine.connect() as conn:
            assert (
                conn.execute(text("SELECT COUNT(*) FROM relationship_evidence WHERE id = 'ev-imm'")).scalar_one() == 1
            )
            assert (
                conn.execute(text("SELECT COUNT(*) FROM relationship_assertions WHERE id = 'as-imm'")).scalar_one() == 1
            )

    @staticmethod
    def test_trigger_names_stable(schema_engine: Engine):
        """Trigger naming helper stays aligned with installed guards."""
        init_db(schema_engine)
        for table in GRAC_TABLE_NAMES:
            update_name, delete_name, truncate_name = list_immutability_trigger_names(table)
            assert update_name.endswith("_u")
            assert delete_name.endswith("_d")
            assert truncate_name.endswith("_t")
            assert len(update_name.encode("utf-8")) <= 63
            assert len(delete_name.encode("utf-8")) <= 63
            assert len(truncate_name.encode("utf-8")) <= 63
            assert table in update_name


@pytest.mark.integration
class TestRelationshipAssertionOrmRoundTrip:
    """ORM insert path works after schema ensure."""

    @staticmethod
    def test_orm_insert_after_init(schema_engine: Engine):
        """Mapped inserts succeed on a fully initialized engine."""
        init_db(schema_engine)
        now = datetime.now(tz=UTC)
        with schema_engine.begin() as conn:
            conn.execute(
                AssetORM.__table__.insert().values(
                    id="A1",
                    symbol="A1",
                    name="Asset",
                    asset_class="equity",
                    sector="Tech",
                    price=1.0,
                    currency="USD",
                )
            )
            conn.execute(
                RebuildJobORM.__table__.insert().values(
                    job_id="job-orm",
                    requested_by="tester",
                    status="succeeded",
                    created_at=now,
                    updated_at=now,
                )
            )
            conn.execute(
                RelationshipEvidenceORM.__table__.insert().values(
                    id="ev-orm",
                    source_ref="ref",
                    content_sha256=DIGEST,
                    media_type="text/plain",
                    visibility="public",
                    custody_id="c",
                    recorded_at=now,
                )
            )
            conn.execute(
                RelationshipAssertionORM.__table__.insert().values(
                    id="as-orm",
                    predicate_id="financial.bond.issuer_reference@1",
                    subject_id="AAPL_BOND_2030",
                    object_id="AAPL",
                    method_id="bond.issuer_id.resolution@1",
                    proposition="prop",
                    confidence_status="not_assessed",
                    effective_from=now,
                    recorded_at=now,
                )
            )
