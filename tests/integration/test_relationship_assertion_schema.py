"""Integration tests for GRAC v1 assertion schema bootstrap and immutability."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.data.base import Base
from src.data.database import init_db, verify_database_schema
from src.data.db_models import AssetORM, RebuildJobORM
from src.data.migrations import _status_constraint_is_canonical
from src.data.relationship_assertion_db_models import (
    EFFECTIVE_WINDOW_CHECK,
    GRAC_TABLE_NAMES,
    STRENGTH_DECIMAL_CHECK,
    RelationshipAssertionEventORM,
    RelationshipAssertionEvidenceORM,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
    RelationshipProjectionEdgeORM,
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.data.relationship_assertion_schema import (
    _ensure_postgresql_grac_constraints,
    _postgresql_check_matches,
    ensure_relationship_assertion_schema,
    list_immutability_trigger_names,
    verify_relationship_assertion_schema,
)
from tests.conftest import enable_sqlite_foreign_keys

UTC = timezone.utc
DIGEST = "c" * 64


@pytest.mark.parametrize("canonical", [EFFECTIVE_WINDOW_CHECK, STRENGTH_DECIMAL_CHECK])
def test_postgresql_grac_constraint_comparison_requires_canonical_predicate(canonical: str) -> None:
    """Named, validated constraints must also preserve the canonical predicate."""
    assert _postgresql_check_matches(f"CHECK (({canonical}))", canonical)
    assert not _postgresql_check_matches("CHECK (TRUE)", canonical)


@pytest.mark.parametrize(
    ("canonical", "catalog_definition"),
    [
        (
            EFFECTIVE_WINDOW_CHECK,
            "CHECK (((effective_to IS NULL) OR (effective_to >= effective_from)))",
        ),
        (
            STRENGTH_DECIMAL_CHECK,
            "CHECK ((((length((strength)::text) >= 1) AND (length((strength)::text) <= 32)) "
            "AND (translate((strength)::text, '0123456789.'::text, ''::text) = ''::text) "
            "AND ((strength)::text !~~ '.%'::text) AND ((strength)::text !~~ '%.'::text) "
            "AND ((strength)::text !~~ '%..%'::text) AND ((strength)::text !~~ '%.%.%'::text) "
            "AND (((strength)::text = '0'::text) OR ((strength)::text = '1'::text) "
            "OR ((strength)::text ~~ '0.%'::text) OR (((strength)::text ~~ '1.%'::text) "
            "AND (replace(substr((strength)::text, 3), '0'::text, ''::text) = ''::text)))))",
        ),
    ],
)
def test_postgresql_grac_constraint_comparison_accepts_catalog_deparse(
    canonical: str,
    catalog_definition: str,
) -> None:
    """Canonical GRAC predicates must match PostgreSQL 17 catalog rendering."""
    assert _postgresql_check_matches(catalog_definition, canonical)


def test_postgresql_grac_constraint_comparison_preserves_boolean_grouping() -> None:
    """PostgreSQL CHECK comparison must reject precedence-changing regrouping."""
    assert not _postgresql_check_matches(
        "CHECK ((a = 1 OR b = 1) AND c = 1)",
        "CHECK (a = 1 OR (b = 1 AND c = 1))",
    )


def test_postgresql_grac_constraint_comparison_accepts_quoted_lowercase_identifiers() -> None:
    """PostgreSQL-safe identifier quotes must not create false schema drift."""
    assert _postgresql_check_matches(
        'CHECK (("effective_to" IS NULL) OR ("effective_to" >= "effective_from"))',
        EFFECTIVE_WINDOW_CHECK,
    )


def test_postgresql_rebuild_status_comparison_accepts_catalog_deparse() -> None:
    """The rebuild status verifier must accept PostgreSQL 17 ANY/ARRAY rendering."""
    definition = (
        "CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, "
        "'running'::character varying, 'succeeded'::character varying, "
        "'failed'::character varying, 'cancel_requested'::character varying, "
        "'cancelled'::character varying])::text[])))"
    )
    assert _status_constraint_is_canonical({"name": "ck_rebuild_jobs_status", "sqltext": definition})


def test_postgresql_grac_migration_skips_already_validated_constraints() -> None:
    """Repeat operator runs must not rescan matching, validated GRAC constraints."""
    connection = MagicMock()
    connection.execute.return_value.all.return_value = [
        (
            "relationship_assertions",
            "ck_relationship_assertions_effective_window",
            f"CHECK (({EFFECTIVE_WINDOW_CHECK}))",
            True,
        ),
        (
            "relationship_projection_edges",
            "ck_relationship_projection_edges_strength",
            f"CHECK (({STRENGTH_DECIMAL_CHECK}))",
            True,
        ),
    ]

    _ensure_postgresql_grac_constraints(connection)

    assert connection.execute.call_count == 1


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
        "ck_relationship_assertions_effective_window",
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
        "ix_relationship_assertion_events_successor_assertion_id",
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
    """Return the reflected table names for the supplied test engine."""
    return set(inspect(engine).get_table_names())


def _check_names(engine: Engine, table: str) -> set[str]:
    """Return named CHECK constraints reflected for one table."""
    return {item["name"] for item in inspect(engine).get_check_constraints(table)}


def _index_names(engine: Engine, table: str) -> set[str]:
    """Return named indexes and unique constraints reflected for one table."""
    names = {item["name"] for item in inspect(engine).get_indexes(table) if item.get("name")}
    # UniqueConstraints may appear as unique indexes depending on dialect.
    for uk in inspect(engine).get_unique_constraints(table):
        if uk.get("name"):
            names.add(uk["name"])
    return names


def _fk_pairs(engine: Engine, table: str) -> set[tuple[str, str]]:
    """Return local-to-remote column pairs for reflected foreign keys."""
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


def _seed_immutability_rows(engine: Engine, now: datetime) -> None:
    """Insert one linked row into each immutable source-of-truth table."""
    with engine.begin() as conn:
        conn.execute(
            RelationshipEvidenceORM.__table__.insert().values(
                id="ev-imm",
                source_ref="ref",
                content_sha256=DIGEST,
                media_type="text/plain",
                visibility="internal",
                custody_id="custody",
                recorded_at=now,
            )
        )
        conn.execute(
            RelationshipAssertionORM.__table__.insert().values(
                id="as-imm",
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
        conn.execute(
            RelationshipAssertionEventORM.__table__.insert().values(
                id="evt-imm",
                assertion_id="as-imm",
                sequence=1,
                from_state=None,
                to_state="Proposed",
                authority="proposer",
                actor_id="actor",
                rationale="propose",
                policy_version="grac.v1-policy",
                recorded_at=now,
            )
        )
        conn.execute(
            RelationshipAssertionEvidenceORM.__table__.insert().values(
                id="link-imm",
                assertion_id="as-imm",
                evidence_id="ev-imm",
                polarity="supporting",
                recorded_at=now,
            )
        )


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

    @staticmethod
    def test_verifier_rejects_missing_guard_without_repair(schema_engine: Engine):
        """Read-only verification must report, not reinstall, a missing SQLite trigger."""
        if schema_engine.dialect.name != "sqlite":
            pytest.skip("SQLite-specific no-repair proof")
        init_db(schema_engine)
        update_trigger, _delete_trigger, _truncate_trigger = list_immutability_trigger_names("relationship_assertions")
        with schema_engine.begin() as connection:
            connection.execute(text(f"DROP TRIGGER {update_trigger}"))

        with pytest.raises(RuntimeError, match="immutability guards are incomplete"):
            verify_relationship_assertion_schema(schema_engine)

        with schema_engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name = :name"),
                {"name": update_trigger},
            ).scalar_one()
        assert remaining == 0

    @staticmethod
    def test_upgrade_backfills_legacy_projection_scopes(schema_engine: Engine):
        """Adding governed_scopes preserves canonical metadata and restores guards."""
        now = datetime.now(tz=UTC)
        Base.metadata.create_all(schema_engine)
        with schema_engine.begin() as conn:
            conn.execute(
                RelationshipAssertionORM.__table__.insert().values(
                    id="as-legacy",
                    predicate_id="financial.bond.issuer_reference@1",
                    subject_id="bond-1",
                    object_id="issuer-1",
                    method_id="method-1",
                    proposition="legacy assertion",
                    confidence_bp=None,
                    confidence_type=None,
                    confidence_method=None,
                    confidence_status="not_assessed",
                    effective_from=now,
                    effective_to=None,
                    recorded_at=now,
                )
            )
            conn.execute(
                RelationshipProjectionRevisionORM.__table__.insert(),
                [
                    {
                        "id": "rev-with-edge",
                        "purpose": "current_view",
                        "effective_at": now,
                        "known_at": now,
                        "contract_version": "grac.v1",
                        "projector_version": "projector.v2",
                        "edge_set_hash": DIGEST,
                        "projection_hash": DIGEST,
                        "created_at": now,
                    },
                    {
                        "id": "rev-empty",
                        "purpose": "current_view",
                        "effective_at": now,
                        "known_at": now,
                        "contract_version": "grac.v1",
                        "projector_version": "projector.v2",
                        "edge_set_hash": DIGEST,
                        "projection_hash": DIGEST,
                        "created_at": now,
                    },
                ],
            )
            conn.execute(
                RelationshipProjectionEdgeORM.__table__.insert().values(
                    id="edge-legacy",
                    revision_id="rev-with-edge",
                    source_id="bond-1",
                    target_id="issuer-1",
                    edge_type="issuer_reference",
                    strength="0.8",
                    direction="subject_to_object",
                    assertion_id="as-legacy",
                )
            )
            conn.execute(
                RebuildJobORM.__table__.insert(),
                [
                    {
                        "job_id": "job-a",
                        "requested_by": "tester",
                        "status": "succeeded",
                        "created_at": now,
                        "updated_at": now,
                    },
                    {
                        "job_id": "job-z",
                        "requested_by": "tester",
                        "status": "succeeded",
                        "created_at": now,
                        "updated_at": now,
                    },
                ],
            )
            conn.execute(
                RelationshipProjectionPublicationORM.__table__.insert(),
                [
                    {
                        "id": "pub-source",
                        "revision_id": "rev-with-edge",
                        "rebuild_job_id": "job-a",
                        "published_at": now,
                    },
                    {
                        "id": "pub-empty",
                        "revision_id": "rev-empty",
                        "rebuild_job_id": "job-z",
                        "published_at": now,
                    },
                ],
            )
            conn.execute(text("ALTER TABLE relationship_projection_revisions DROP COLUMN governed_scopes"))

        ensure_relationship_assertion_schema(schema_engine)

        with schema_engine.connect() as conn:
            scopes = conn.execute(
                text("SELECT id, governed_scopes FROM relationship_projection_revisions ORDER BY id")
            ).all()
        assert scopes == [
            ("rev-empty", '[{"predicate_id":"financial.bond.issuer_reference@1","purpose":"current_view"}]'),
            (
                "rev-with-edge",
                '[{"predicate_id":"financial.bond.issuer_reference@1","purpose":"current_view"}]',
            ),
        ]
        forbidden_update = text("UPDATE relationship_projection_revisions SET purpose = 'changed'")
        with pytest.raises((DBAPIError, IntegrityError)), schema_engine.begin() as conn:
            conn.execute(forbidden_update)


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

    @staticmethod
    def test_postgresql_access_hardening(schema_engine: Engine):
        """PostgreSQL GRAC tables are RLS-protected with no public policies or grants."""
        if schema_engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL-only RLS catalog assertion")
        init_db(schema_engine)
        with schema_engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT c.relname, c.relrowsecurity, count(p.oid), bool_or(acl.grantee = 0) "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "LEFT JOIN pg_policy p ON p.polrelid = c.oid "
                    "LEFT JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) acl ON true "
                    "WHERE n.nspname = current_schema() AND c.relname = ANY(:tables) "
                    "GROUP BY c.relname, c.relrowsecurity"
                ),
                {"tables": list(GRAC_TABLE_NAMES)},
            ).all()
            function_config = conn.execute(
                text(
                    "SELECT proconfig FROM pg_proc WHERE proname = 'grac_v1_reject_mutation' "
                    "AND pronamespace = current_schema()::regnamespace"
                )
            ).scalar_one()
        assert {row[0] for row in rows} == set(GRAC_TABLE_NAMES)
        assert all(row[1] and row[2] == 0 and not row[3] for row in rows)
        assert "search_path=pg_catalog" in (function_config or [])

    @staticmethod
    def test_postgresql_verifier_cold_start_and_restart_in_read_only_transactions(schema_engine: Engine):
        """PostgreSQL compatibility verification must succeed with writes disabled."""
        if schema_engine.dialect.name != "postgresql":
            pytest.skip("PostgreSQL-only read-only transaction proof")
        init_db(schema_engine)
        pg_url = _postgres_url()
        assert pg_url is not None

        for _restart in range(2):
            runtime_engine = create_engine(
                pg_url,
                future=True,
                connect_args={"options": "-c default_transaction_read_only=on"},
            )
            try:
                verify_database_schema(runtime_engine)
            finally:
                runtime_engine.dispose()


@pytest.mark.integration
class TestRelationshipAssertionImmutability:
    """UPDATE/DELETE must be rejected on guarded tables."""

    @staticmethod
    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE relationship_evidence SET media_type = 'application/json' WHERE id = 'ev-imm'",
            "DELETE FROM relationship_evidence WHERE id = 'ev-imm'",
            "UPDATE relationship_assertions SET proposition = 'changed' WHERE id = 'as-imm'",
            "DELETE FROM relationship_assertions WHERE id = 'as-imm'",
            "UPDATE relationship_assertion_events SET rationale = 'changed' WHERE id = 'evt-imm'",
            "DELETE FROM relationship_assertion_events WHERE id = 'evt-imm'",
            "UPDATE relationship_assertion_evidence SET polarity = 'opposing' WHERE id = 'link-imm'",
            "DELETE FROM relationship_assertion_evidence WHERE id = 'link-imm'",
        ],
        ids=[
            "update-evidence",
            "delete-evidence",
            "update-assertion",
            "delete-assertion",
            "update-event",
            "delete-event",
            "update-evidence-link",
            "delete-evidence-link",
        ],
    )
    def test_update_and_delete_rejected(schema_engine: Engine, statement: str):
        """Immutability triggers reject every source-of-truth row mutation."""
        init_db(schema_engine)
        _seed_immutability_rows(schema_engine, datetime.now(tz=UTC))

        def _execute(statement: str) -> None:
            """Execute one attempted immutable-row mutation in a transaction."""
            with schema_engine.begin() as conn:
                conn.execute(text(statement))

        with pytest.raises((IntegrityError, DBAPIError)):
            _execute(statement)

        # Rows remain after failed mutations.
        count_queries = {
            "relationship_evidence": text("SELECT COUNT(*) FROM relationship_evidence"),
            "relationship_assertions": text("SELECT COUNT(*) FROM relationship_assertions"),
            "relationship_assertion_events": text("SELECT COUNT(*) FROM relationship_assertion_events"),
            "relationship_assertion_evidence": text("SELECT COUNT(*) FROM relationship_assertion_evidence"),
        }
        with schema_engine.connect() as conn:
            counts = {table: conn.execute(query).scalar_one() for table, query in count_queries.items()}
        assert counts == {
            "relationship_evidence": 1,
            "relationship_assertions": 1,
            "relationship_assertion_events": 1,
            "relationship_assertion_evidence": 1,
        }

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
