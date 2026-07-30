"""Unit tests for GRAC v1 relationship assertion ORM models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    GRAC_TABLE_NAMES,
    RelationshipAssertionEventORM,
    RelationshipAssertionEvidenceORM,
    RelationshipAssertionORM,
    RelationshipEvidenceORM,
    RelationshipProjectionEdgeORM,
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.data.relationship_assertion_schema import (
    _UNTRUSTED_DATABASE_ROLES_ENV,
    _expected_postgresql_trigger_bindings,
    _expected_postgresql_trigger_names,
    _expected_sqlite_trigger_bindings,
    _expected_sqlite_trigger_names,
    _postgresql_guards_present,
    _revoke_immutability_function_execute,
    _sqlite_guards_present,
    _untrusted_database_roles,
)

UTC = timezone.utc

pytest.importorskip("sqlalchemy")

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


@pytest.fixture
def db_session(tmp_path):
    """Create a temporary SQLite session with GRAC schema initialized."""
    db_path = tmp_path / "grac_models.db"
    engine = create_engine_from_url(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _add_evidence(session, evidence_id: str = "ev-1") -> RelationshipEvidenceORM:
    row = RelationshipEvidenceORM(
        id=evidence_id,
        source_ref="sample://AAPL_BOND_2030",
        content_sha256=DIGEST_A,
        media_type="application/json",
        visibility="internal",
        custody_id="collector-1",
        recorded_at=_utcnow(),
    )
    session.add(row)
    session.flush()
    return row


@dataclass(frozen=True)
class _AssertionConfidence:
    """Optional confidence fields for assertion test helpers."""

    status: str = "not_assessed"
    bp: int | None = None
    confidence_type: str | None = None
    method: str | None = None


def _add_assertion(
    session,
    assertion_id: str = "as-1",
    confidence: _AssertionConfidence | None = None,
) -> RelationshipAssertionORM:
    conf = confidence or _AssertionConfidence()
    row = RelationshipAssertionORM(
        id=assertion_id,
        predicate_id="financial.bond.issuer_reference@1",
        subject_id="AAPL_BOND_2030",
        object_id="AAPL",
        method_id="bond.issuer_id.resolution@1",
        proposition="Bond issuer_id references AAPL",
        confidence_bp=conf.bp,
        confidence_type=conf.confidence_type,
        confidence_method=conf.method,
        confidence_status=conf.status,
        effective_from=_utcnow(),
        recorded_at=_utcnow(),
    )
    session.add(row)
    session.flush()
    return row


def test_grac_table_names_cover_seven_tables() -> None:
    """Exactly seven additive GRAC tables must be registered."""
    assert len(GRAC_TABLE_NAMES) == 7
    assert "relationship_evidence" in GRAC_TABLE_NAMES
    assert "relationship_projection_publications" in GRAC_TABLE_NAMES


def test_confidence_shape_check_rejects_assessed_without_bp() -> None:
    """Assessed confidence requires basis points and method metadata."""
    engine = create_engine_from_url("sqlite:///:memory:")
    init_db(engine)
    now = datetime.now(timezone.utc)
    insert_stmt = RelationshipAssertionORM.__table__.insert().values(
        id="11111111-1111-1111-1111-111111111111",
        predicate_id="financial.bond.issuer_reference@1",
        subject_id="AAPL_BOND_2030",
        object_id="AAPL",
        method_id="bond.issuer_id.resolution@1",
        proposition="issuer reference",
        confidence_bp=None,
        confidence_type=None,
        confidence_method=None,
        confidence_status="assessed",
        effective_from=now,
        effective_to=None,
        recorded_at=now,
    )
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(insert_stmt)
    engine.dispose()


def test_effective_window_rejects_end_before_start() -> None:
    """Assertions cannot end before their effective start."""
    engine = create_engine_from_url("sqlite:///:memory:")
    init_db(engine)
    now = datetime.now(timezone.utc)
    values = {
        "id": "12121212-1212-1212-1212-121212121212",
        "predicate_id": "financial.bond.issuer_reference@1",
        "subject_id": "AAPL_BOND_2030",
        "object_id": "AAPL",
        "method_id": "bond.issuer_id.resolution@1",
        "proposition": "issuer reference",
        "confidence_status": "not_assessed",
        "effective_from": now,
        "effective_to": now - timedelta(seconds=1),
        "recorded_at": now,
    }
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(RelationshipAssertionORM.__table__.insert().values(**values))
    engine.dispose()


@pytest.mark.parametrize("bad_digest", ["NOT-A-DIGEST", "Z" * 64, "A" * 64])
def test_evidence_digest_check_requires_lowercase_hex_sha256(bad_digest: str) -> None:
    """Evidence digests must be 64-char lowercase hexadecimal."""
    engine = create_engine_from_url("sqlite:///:memory:")
    init_db(engine)
    now = datetime.now(timezone.utc)
    insert_stmt = RelationshipEvidenceORM.__table__.insert().values(
        id="22222222-2222-2222-2222-222222222222",
        source_ref="sample://aapl-bond",
        content_sha256=bad_digest,
        media_type="application/json",
        observed_at=None,
        issued_at=None,
        visibility="public",
        licensing=None,
        reuse_policy=None,
        custody_id="collector-1",
        recorded_at=now,
    )
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(insert_stmt)
    engine.dispose()


def test_sqlite_engine_enforces_foreign_keys_by_default() -> None:
    """Production SQLite engines must enable PRAGMA foreign_keys."""
    engine = create_engine_from_url("sqlite:///:memory:")
    with engine.connect() as connection:
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert int(enabled or 0) == 1
    engine.dispose()


def test_init_db_attaches_sqlite_hooks_for_plain_engines() -> None:
    """init_db must register translate/FK hooks even for plain create_engine."""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            RelationshipEvidenceORM.__table__.insert().values(
                id="33333333-3333-3333-3333-333333333333",
                source_ref="sample://plain-engine",
                content_sha256=DIGEST_A,
                media_type="application/json",
                observed_at=None,
                issued_at=None,
                visibility="public",
                licensing=None,
                reuse_policy=None,
                custody_id="collector-1",
                recorded_at=now,
            )
        )
    engine.dispose()


@pytest.mark.unit
class TestRelationshipAssertionTableRegistration:
    """ORM table names and metadata registration."""

    @staticmethod
    def test_tables_created_by_init_db(tmp_path):
        """init_db creates all seven GRAC tables."""
        engine = create_engine_from_url(f"sqlite:///{tmp_path / 'fresh.db'}")
        init_db(engine)
        names = set(inspect(engine).get_table_names())
        assert set(GRAC_TABLE_NAMES).issubset(names)
        engine.dispose()


@pytest.mark.unit
class TestRelationshipEvidenceORM:
    """Evidence row constraints."""

    @staticmethod
    def test_insert_evidence(db_session):
        """Evidence rows persist without body bytes."""
        _add_evidence(db_session)
        db_session.commit()
        loaded = db_session.get(RelationshipEvidenceORM, "ev-1")
        assert loaded is not None
        assert loaded.content_sha256 == DIGEST_A
        assert not hasattr(loaded, "body")

    @staticmethod
    def test_invalid_visibility_rejected(db_session):
        """Visibility check rejects unknown values."""
        db_session.add(
            RelationshipEvidenceORM(
                id="ev-bad",
                source_ref="x",
                content_sha256=DIGEST_A,
                media_type="text/plain",
                visibility="secret",
                custody_id="c",
                recorded_at=_utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()


@pytest.mark.unit
class TestRelationshipAssertionORM:
    """Assertion confidence and identity constraints."""

    @staticmethod
    def test_not_assessed_requires_null_confidence(db_session):
        """not_assessed forbids confidence_bp."""
        _add_assertion(db_session)
        db_session.commit()
        loaded = db_session.get(RelationshipAssertionORM, "as-1")
        assert loaded is not None
        assert loaded.confidence_status == "not_assessed"
        assert loaded.confidence_bp is None

    @staticmethod
    def test_assessed_requires_confidence_fields(db_session):
        """assessed requires bp/type/method."""
        _add_assertion(
            db_session,
            confidence=_AssertionConfidence(
                status="assessed",
                bp=8000,
                confidence_type="model",
                method="issuer.confidence@1",
            ),
        )
        db_session.commit()
        loaded = db_session.get(RelationshipAssertionORM, "as-1")
        assert loaded is not None
        assert loaded.confidence_bp == 8000

    @staticmethod
    def test_confidence_bp_out_of_range_rejected(db_session):
        """confidence_bp above 10000 fails CHECK."""
        db_session.add(
            RelationshipAssertionORM(
                id="as-range",
                predicate_id="financial.bond.issuer_reference@1",
                subject_id="AAPL_BOND_2030",
                object_id="AAPL",
                method_id="bond.issuer_id.resolution@1",
                proposition="x",
                confidence_status="assessed",
                confidence_bp=10001,
                confidence_type="model",
                confidence_method="m",
                effective_from=_utcnow(),
                recorded_at=_utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()


@pytest.mark.unit
class TestRelationshipAssertionLinksAndEvents:
    """Evidence links, events, and projection rows."""

    @staticmethod
    def test_evidence_link_and_event(db_session):
        """Polarity links and sequenced events can be inserted."""
        _add_evidence(db_session)
        _add_assertion(db_session)
        db_session.add(
            RelationshipAssertionEvidenceORM(
                id="link-1",
                assertion_id="as-1",
                evidence_id="ev-1",
                polarity="supporting",
                recorded_at=_utcnow(),
            )
        )
        db_session.add(
            RelationshipAssertionEventORM(
                id="evt-1",
                assertion_id="as-1",
                sequence=1,
                from_state=None,
                to_state="Proposed",
                authority="proposer",
                actor_id="user-1",
                rationale="initial proposal",
                policy_version="policy.v1",
                recorded_at=_utcnow(),
                correlation_id="corr-1",
            )
        )
        db_session.commit()
        assert db_session.get(RelationshipAssertionEvidenceORM, "link-1") is not None
        assert db_session.get(RelationshipAssertionEventORM, "evt-1") is not None

    @staticmethod
    def test_duplicate_event_sequence_rejected(db_session):
        """Event sequence is unique per assertion."""
        _add_assertion(db_session)
        for event_id in ("evt-1", "evt-2"):
            db_session.add(
                RelationshipAssertionEventORM(
                    id=event_id,
                    assertion_id="as-1",
                    sequence=1,
                    from_state=None,
                    to_state="Proposed",
                    authority="proposer",
                    actor_id="user-1",
                    rationale="dup",
                    policy_version="policy.v1",
                    recorded_at=_utcnow(),
                )
            )
        with pytest.raises(IntegrityError):
            db_session.commit()

    @staticmethod
    def test_projection_revision_edge_and_publication(db_session):
        """Revision, edge, and publication rows insert with FK targets."""
        _add_assertion(db_session)
        now = _utcnow()
        db_session.add(
            RebuildJobORM(
                job_id="job-1",
                requested_by="tester",
                status="succeeded",
                created_at=now,
                updated_at=now,
                execution_id="exec-1",
            )
        )
        db_session.add(
            RelationshipProjectionRevisionORM(
                id="rev-1",
                purpose="financial_graph_current_view",
                effective_at=now,
                known_at=now,
                contract_version="grac.v1",
                projector_version="projector.v1",
                edge_set_hash=DIGEST_A,
                projection_hash=DIGEST_B,
                created_at=now,
            )
        )
        db_session.flush()
        db_session.add(
            RelationshipProjectionEdgeORM(
                id="edge-1",
                revision_id="rev-1",
                source_id="AAPL_BOND_2030",
                target_id="AAPL",
                edge_type="corporate_link",
                strength="0.8",
                direction="subject_to_object",
                assertion_id="as-1",
            )
        )
        db_session.add(
            RelationshipProjectionPublicationORM(
                id="pub-1",
                revision_id="rev-1",
                rebuild_job_id="job-1",
                published_at=now,
                execution_id="exec-1",
            )
        )
        db_session.commit()
        assert db_session.get(RelationshipProjectionPublicationORM, "pub-1") is not None

    @staticmethod
    def test_invalid_polarity_rejected(db_session):
        """Polarity check rejects unknown values."""
        _add_evidence(db_session)
        _add_assertion(db_session)
        db_session.add(
            RelationshipAssertionEvidenceORM(
                id="link-bad",
                assertion_id="as-1",
                evidence_id="ev-1",
                polarity="neutral",
                recorded_at=_utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()

    @staticmethod
    def test_invalid_strength_rejected(db_session):
        """Edge strength must be within the closed zero-to-one interval."""
        _add_assertion(db_session)
        now = _utcnow()
        db_session.add(
            RelationshipProjectionRevisionORM(
                id="rev-bad-str",
                purpose="financial_graph_current_view",
                effective_at=now,
                known_at=now,
                contract_version="grac.v1",
                projector_version="projector.v1",
                edge_set_hash=DIGEST_A,
                projection_hash=DIGEST_B,
                created_at=now,
            )
        )
        db_session.flush()
        db_session.add(
            RelationshipProjectionEdgeORM(
                id="edge-bad",
                revision_id="rev-bad-str",
                source_id="AAPL_BOND_2030",
                target_id="AAPL",
                edge_type="corporate_link",
                strength="1.1",
                direction="subject_to_object",
                assertion_id="as-1",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()

    @staticmethod
    def test_multi_dot_strength_rejected(db_session):
        """Strength strings with more than one decimal point are rejected."""
        _add_assertion(db_session)
        now = _utcnow()
        db_session.add(
            RelationshipProjectionRevisionORM(
                id="rev-multi-dot",
                purpose="financial_graph_current_view",
                effective_at=now,
                known_at=now,
                contract_version="grac.v1",
                projector_version="projector.v1",
                edge_set_hash=DIGEST_A,
                projection_hash=DIGEST_B,
                created_at=now,
            )
        )
        db_session.flush()
        db_session.add(
            RelationshipProjectionEdgeORM(
                id="edge-multi-dot",
                revision_id="rev-multi-dot",
                source_id="AAPL_BOND_2030",
                target_id="AAPL",
                edge_type="corporate_link",
                strength="1.2.3",
                direction="subject_to_object",
                assertion_id="as-1",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()


def test_revoke_immutability_execute_raises_when_public_retains_privilege() -> None:
    """Privilege repair must fail loud if PUBLIC/untrusted EXECUTE cannot be revoked."""
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = True
    with pytest.raises(PermissionError, match="PUBLIC/untrusted EXECUTE"):
        _revoke_immutability_function_execute(connection)


def test_revoke_immutability_execute_scopes_acl_check_to_current_schema() -> None:
    """EXECUTE verification must cover PUBLIC and untrusted roles in the current schema only."""
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = False

    _revoke_immutability_function_execute(connection)

    assert connection.execute.call_count == 2
    revoke_sql = str(connection.execute.call_args_list[0].args[0])
    acl_sql = str(connection.execute.call_args_list[1].args[0])
    acl_params = connection.execute.call_args_list[1].args[1]
    assert "pg_catalog.current_schema()" in revoke_sql
    assert "%I.%I()" in revoke_sql
    assert "undefined_object" in revoke_sql
    assert "'anon'" in revoke_sql
    assert "'authenticated'" in revoke_sql
    assert "pg_catalog.current_schema()" in acl_sql
    assert "pg_namespace" in acl_sql
    assert "pronargs = 0" in acl_sql
    assert "acl.grantee = 0" in acl_sql
    assert "has_function_privilege" in acl_sql
    assert "pg_roles" in acl_sql
    assert "rolname IN" in acl_sql
    assert "roles" in acl_sql
    assert acl_params["roles"] == ["anon", "authenticated"]


def test_postgresql_guards_present_scopes_triggers_to_current_schema() -> None:
    """Guard presence must ignore matching trigger names outside current-schema GRAC tables."""
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    connection.execute.return_value.fetchall.return_value = []

    assert _postgresql_guards_present(connection) is False

    assert connection.execute.call_count == 2
    trigger_sql = str(connection.execute.call_args_list[1].args[0])
    trigger_params = connection.execute.call_args_list[1].args[1]
    assert "pg_catalog.current_schema()" in trigger_sql
    assert "pg_class" in trigger_sql
    assert "pg_namespace" in trigger_sql
    assert "fn_ns" in trigger_sql
    assert "c.relname IN" in trigger_sql
    assert "NOT t.tgisinternal" in trigger_sql
    assert "tgenabled" in trigger_sql
    assert "IN ('O', 'A')" in trigger_sql
    assert "<> 'D'" not in trigger_sql
    assert "tgtype" in trigger_sql
    assert "tgfoid" in trigger_sql
    assert "pronamespace" in trigger_sql
    assert trigger_params["tables"] == list(GRAC_TABLE_NAMES)
    assert trigger_params["fn"] == "grac_v1_reject_mutation"
    assert set(trigger_params["names"]) == set(_expected_postgresql_trigger_names())


def test_postgresql_guards_present_requires_origin_or_always_enabled() -> None:
    """Replica-only (R) and disabled (D) triggers must not satisfy guard presence."""
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    connection.execute.return_value.fetchall.return_value = []

    assert _postgresql_guards_present(connection) is False

    trigger_sql = str(connection.execute.call_args_list[1].args[0])
    assert "t.tgenabled IN ('O', 'A')" in trigger_sql


def test_postgresql_guards_present_requires_function_in_current_schema() -> None:
    """Trigger function must live in current schema, not only match proname/pronargs."""
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    connection.execute.return_value.fetchall.return_value = []

    assert _postgresql_guards_present(connection) is False

    fn_sql = str(connection.execute.call_args_list[0].args[0])
    trigger_sql = str(connection.execute.call_args_list[1].args[0])
    assert "n.nspname = pg_catalog.current_schema()" in fn_sql
    assert "fn_ns.nspname = pg_catalog.current_schema()" in trigger_sql
    assert "p.pronamespace" in trigger_sql


def test_postgresql_guards_present_requires_correct_table_and_event() -> None:
    """A matching trigger name on the wrong table/event must not count as installed."""
    connection = MagicMock()
    connection.execute.return_value.first.return_value = (1,)
    expected = _expected_postgresql_trigger_bindings()
    swap_name, swap_table, swap_event = next(
        (name, table, event) for name, table, event in expected if event == "UPDATE"
    )
    other = next(table for table in GRAC_TABLE_NAMES if table != swap_table)
    wrong_rows: list[tuple[str, str, str]] = [
        (swap_name, other, swap_event) if name == swap_name else (name, table, event) for name, table, event in expected
    ]
    connection.execute.return_value.fetchall.return_value = wrong_rows

    assert _postgresql_guards_present(connection) is False


def test_sqlite_guards_present_scopes_triggers_to_grac_tables() -> None:
    """SQLite guard presence must require triggers bound to GRAC table names."""
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = []

    assert _sqlite_guards_present(connection) is False

    sql = str(connection.execute.call_args.args[0])
    params = connection.execute.call_args.args[1]
    assert "sqlite_master" in sql
    assert "tbl_name IN" in sql
    assert "BEFORE UPDATE" in sql
    assert "BEFORE DELETE" in sql
    assert params["tables"] == list(GRAC_TABLE_NAMES)
    assert set(params["names"]) == set(_expected_sqlite_trigger_names())


def test_sqlite_guards_present_requires_name_table_pairing() -> None:
    """SQLite must not accept a correct trigger name attached to another GRAC table."""
    connection = MagicMock()
    expected = _expected_sqlite_trigger_bindings()
    swap_name, swap_table, swap_event = next(iter(expected))
    other = next(table for table in GRAC_TABLE_NAMES if table != swap_table)
    wrong_rows: list[tuple[str, str, str]] = [
        (swap_name, other, swap_event) if name == swap_name else (name, table, event) for name, table, event in expected
    ]
    connection.execute.return_value.fetchall.return_value = wrong_rows

    assert _sqlite_guards_present(connection) is False


def test_sqlite_guards_present_requires_correct_event() -> None:
    """SQLite must not accept a correct name/table pair with the wrong mutation event."""
    connection = MagicMock()
    expected = _expected_sqlite_trigger_bindings()
    swap_name, swap_table, _swap_event = next(
        (name, table, event) for name, table, event in expected if event == "UPDATE"
    )
    wrong_rows: list[tuple[str, str, str]] = [
        (swap_name, swap_table, "DELETE") if name == swap_name else (name, table, event)
        for name, table, event in expected
    ]
    connection.execute.return_value.fetchall.return_value = wrong_rows

    assert _sqlite_guards_present(connection) is False


def test_untrusted_database_roles_honor_fardb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schema privilege repair must use FARDB_UNTRUSTED_DATABASE_ROLES when set."""
    monkeypatch.setenv(_UNTRUSTED_DATABASE_ROLES_ENV, "public_reader, api_user")
    assert _untrusted_database_roles() == ("public_reader", "api_user")

    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = False
    _revoke_immutability_function_execute(connection)

    revoke_sql = str(connection.execute.call_args_list[0].args[0])
    acl_params = connection.execute.call_args_list[1].args[1]
    assert "'public_reader'" in revoke_sql
    assert "'api_user'" in revoke_sql
    assert "'anon'" not in revoke_sql
    assert acl_params["roles"] == ["public_reader", "api_user"]


def test_untrusted_database_roles_reject_unsafe_identity() -> None:
    """Invalid FARDB_UNTRUSTED_DATABASE_ROLES must fail closed."""
    with pytest.raises(ValueError, match=_UNTRUSTED_DATABASE_ROLES_ENV):
        _untrusted_database_roles({_UNTRUSTED_DATABASE_ROLES_ENV: "anon,role;select"})
