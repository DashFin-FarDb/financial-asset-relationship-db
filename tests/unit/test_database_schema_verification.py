"""Unit tests for read-only database schema and authority verification."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
)
from sqlalchemy.engine import Engine

from src.data.database import (
    Base,
    SchemaCompatibilityError,
    _normalize_check_definition,
    _verify_table_constraints,
    _verify_table_schema,
    configure_sqlite_engine,
    create_engine_from_url,
    init_db,
    verify_database_schema,
    verify_runtime_database_authority,
)

pytestmark = pytest.mark.unit


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """Provide an isolated declarative base for test-created table metadata."""
    existing_tables = set(Base.metadata.tables)

    class _IsolatedBase(Base):
        """Declarative base subclass for isolated table definitions."""

        __abstract__ = True

    yield _IsolatedBase

    for table_name in set(Base.metadata.tables) - existing_tables:
        Base.metadata.remove(Base.metadata.tables[table_name])


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Create an in-memory SQLite engine with repository connection hooks."""
    test_engine = configure_sqlite_engine(create_engine("sqlite:///:memory:", future=True))
    yield test_engine
    test_engine.dispose()


@pytest.mark.parametrize(
    "missing_invariant, error_match",
    [
        ("primary_key", "primary-key"),
        ("unique", "uniqueness"),
        ("foreign_key", "foreign-key"),
    ],
)
def test_table_constraint_verifier_rejects_missing_invariants(missing_invariant: str, error_match: str) -> None:
    """Runtime verification must cover PK, exact uniqueness, and FK contracts."""
    metadata = MetaData()
    Table("parent", metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String),
        Column("parent_id", ForeignKey("parent.id")),
        UniqueConstraint("code"),
    )
    inspector = MagicMock()
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    inspector.get_unique_constraints.return_value = [{"column_names": ["code"]}]
    inspector.get_foreign_keys.return_value = [
        {
            "constrained_columns": ["parent_id"],
            "referred_table": "parent",
            "referred_columns": ["id"],
        }
    ]
    if missing_invariant == "primary_key":
        inspector.get_pk_constraint.return_value = {"constrained_columns": []}
    elif missing_invariant == "unique":
        inspector.get_unique_constraints.return_value = []
    else:
        inspector.get_foreign_keys.return_value = []

    with pytest.raises(SchemaCompatibilityError, match=error_match):
        _verify_table_constraints(inspector, "child", child)


def test_check_normalization_accepts_postgresql_any_rendering() -> None:
    """PostgreSQL deparsing should preserve an equivalent literal status domain."""
    expected = "status IN ('pending', 'running', 'cancelled')"
    reflected = (
        "CHECK (((status)::text = ANY ((ARRAY['running'::character varying, "
        "'cancelled'::character varying, 'pending'::character varying])::text[])))"
    )
    assert _normalize_check_definition(reflected) == _normalize_check_definition(expected)


@pytest.mark.parametrize(
    ("mismatch", "error_match"),
    [("check", "incompatible constraints"), ("index", "incompatible indexes")],
)
def test_table_schema_rejects_same_named_definition_drift(
    mismatch: str,
    error_match: str,
    isolated_base: type[Base],
) -> None:
    """Names alone must not admit changed CHECK predicates or index properties."""

    class ContractModel(isolated_base):  # type: ignore[misc]
        """Isolated schema contract for reflected-definition checks."""

        __tablename__ = "definition_contract"
        __table_args__ = (
            CheckConstraint("value >= 0", name="ck_definition_contract_value"),
            Index("ix_definition_contract_value", "value"),
        )
        id = Column(Integer, primary_key=True)
        value = Column(Integer)

    inspector = MagicMock()
    inspector.get_columns.return_value = [{"name": "id"}, {"name": "value"}]
    inspector.get_check_constraints.return_value = [
        {
            "name": "ck_definition_contract_value",
            "sqltext": "value >= 1" if mismatch == "check" else "value >= 0",
        }
    ]
    inspector.get_indexes.return_value = [
        {
            "name": "ix_definition_contract_value",
            "column_names": ["id" if mismatch == "index" else "value"],
            "unique": False,
        }
    ]
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    inspector.get_unique_constraints.return_value = []
    inspector.get_foreign_keys.return_value = []

    with pytest.raises(SchemaCompatibilityError, match=error_match):
        _verify_table_schema(inspector, ContractModel.__tablename__)


def test_runtime_verifier_accepts_initialized_schema(engine: Engine) -> None:
    """Explicit migration output should satisfy the read-only runtime verifier."""
    init_db(engine)

    verify_database_schema(engine)


def test_runtime_verifier_fails_without_creating_schema(tmp_path) -> None:
    """An empty runtime database should fail closed and remain empty."""
    empty_engine = create_engine_from_url(f"sqlite:///{tmp_path / 'empty-runtime.db'}")
    try:
        with pytest.raises(SchemaCompatibilityError, match="missing required tables"):
            verify_database_schema(empty_engine)

        assert inspect(empty_engine).get_table_names() == []
    finally:
        empty_engine.dispose()


def test_runtime_verifier_supports_query_only_cold_start_and_restart(tmp_path) -> None:
    """A migrated SQLite database verifies twice with persistent writes prohibited."""
    database_url = f"sqlite:///{tmp_path / 'query-only-runtime.db'}"
    migration_engine = create_engine_from_url(database_url)
    init_db(migration_engine)
    migration_engine.dispose()

    def _make_query_only(dbapi_connection, _connection_record) -> None:
        """Force each runtime connection into SQLite query-only mode."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only=ON")
        cursor.close()

    for _restart in range(2):
        runtime_engine = create_engine_from_url(database_url)
        event.listen(runtime_engine, "connect", _make_query_only)

        try:
            verify_database_schema(runtime_engine)
            with runtime_engine.connect() as connection:
                assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
        finally:
            runtime_engine.dispose()


@pytest.mark.parametrize("restricted", [False, True], ids=["privileged", "restricted"])
def test_postgresql_runtime_authority_posture(restricted: bool) -> None:
    """PostgreSQL runtime authority must reject privileged and accept restricted roles."""
    runtime_engine = Mock(spec=Engine)
    runtime_engine.url = "postgresql://runtime:secret@database.invalid/fardb"
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = restricted
    runtime_engine.connect.return_value.__enter__ = MagicMock(return_value=connection)
    runtime_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    if not restricted:
        with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
            verify_runtime_database_authority(runtime_engine)
        return

    verify_runtime_database_authority(runtime_engine)
    authority_query = str(connection.execute.call_args.args[0])
    assert "current_schema() IS NOT NULL" in authority_query
    assert "login.rolname = session_user" in authority_query
    assert "pg_has_role(login.oid, assumable.oid, 'MEMBER')" in authority_query
    assert "namespace.nspowner = assumable.oid" in authority_query
    assert "database.datdba = assumable.oid" in authority_query
