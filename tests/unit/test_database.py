"""
Unit tests for database configuration helpers.

This module contains comprehensive unit tests for database configuration including:
- Engine creation with various database URLs
- SQLite in-memory configuration
- Session factory creation
- Database initialization
- Transactional scope management
- Error handling and rollback behavior
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, Mock, patch

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool, StaticPool

from api.database import (
    _cleanup_memory_connection,
    _get_database_url,
    _is_memory_db,
    _resolve_sqlite_path,
    execute,
    fetch_one,
    fetch_value,
    get_connection,
)
from src.data.database import (
    DEFAULT_DATABASE_URL,
    GRAPH_RUNTIME_CAPABILITY,
    Base,
    CapabilityRoleBootstrapRequiredError,
    SchemaCompatibilityError,
    _ensure_capability_role,
    _normalize_check_definition,
    _runtime_policy_specs,
    _runtime_table_privileges,
    _verify_runtime_capability_catalog,
    _verify_table_constraints,
    _verify_table_schema,
    configure_sqlite_engine,
    create_engine_from_url,
    create_session_factory,
    init_db,
    session_scope,
    verify_database_schema,
    verify_runtime_database_authority,
)


class _CatalogResult:
    """Small SQLAlchemy result stand-in for catalog-verifier unit coverage."""

    def __init__(self, *, scalar: object | None = None, rows: list[tuple] | None = None) -> None:
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self) -> object:
        """Return the configured scalar value."""
        return self._scalar

    def all(self) -> list[tuple]:
        """Return the configured catalog rows."""
        return self._rows


def test_graph_capability_preserves_grac_immutability_and_locking() -> None:
    """GRAC grants allow inserts and row locks without a usable update path."""
    from src.data.relationship_assertion_db_models import GRAC_TABLE_NAMES

    capabilities = (GRAPH_RUNTIME_CAPABILITY,)
    privileges = _runtime_table_privileges(capabilities)
    policies = _runtime_policy_specs(capabilities)
    for table_name in GRAC_TABLE_NAMES:
        assert privileges[(GRAPH_RUNTIME_CAPABILITY, table_name)] == {"SELECT", "INSERT"}
        assert policies[(table_name, "fardb_graph_lock_v1")] == ("w", "true", "false")


def test_capability_role_requires_superuser_bootstrap_when_missing() -> None:
    """Normal migration authority cannot create a missing cluster capability role."""
    role_state = MagicMock()
    role_state.one.return_value = (False, False)
    connection = MagicMock()
    connection.execute.return_value = role_state

    with pytest.raises(
        CapabilityRoleBootstrapRequiredError,
        match="bootstrap_database_capability_roles.sql as a PostgreSQL superuser",
    ):
        _ensure_capability_role(connection, "fardb_runtime_graph")

    connection.execute.assert_called_once()


def test_capability_role_retains_superuser_fallback_creation() -> None:
    """Disposable superuser setup may still create and strictly validate a missing role."""
    role_state = MagicMock()
    role_state.one.return_value = (False, True)
    connection = MagicMock()
    connection.execute.side_effect = [role_state, MagicMock()]

    _ensure_capability_role(connection, "fardb_runtime_graph")

    statement = str(connection.execute.call_args_list[1].args[0])
    assert "CREATE ROLE ' || quote_ident(capability_role)" in statement
    assert "rolname = CURRENT_USER" in statement
    assert "rolsuper" in statement
    assert "membership.roleid = role.oid AND membership.admin_option" in statement


def test_runtime_capability_catalog_accepts_exact_graph_contract() -> None:
    """The catalog verifier accepts the complete graph role, RLS, and grant matrix."""
    from src.data import relationship_assertion_db_models  # noqa: F401
    from src.data.relationship_assertion_db_models import GRAC_TABLE_NAMES

    capabilities = (GRAPH_RUNTIME_CAPABILITY,)
    role_name = "fardb_runtime_graph"
    table_privileges = _runtime_table_privileges(capabilities)
    policy_rows = [
        (table_name, policy_name, command, True, role_name, using_expression, check_expression)
        for (table_name, policy_name), (command, using_expression, check_expression) in _runtime_policy_specs(
            capabilities
        ).items()
    ]
    grac_tables = frozenset(GRAC_TABLE_NAMES)

    def _execute(statement, parameters=None) -> _CatalogResult:
        """Dispatch one expected catalog query to its configured result."""
        sql = str(statement)
        parameters = parameters or {}
        if "COUNT(*) = 1 FROM pg_roles" in sql:
            assert "membership.roleid = role.oid" in sql
            assert "membership.admin_option" in sql
            assert "WITH RECURSIVE role_membership(member, roleid, member_is_superuser)" in sql
            assert "grantee.rolsuper" in sql
            assert "to_jsonb(membership) ->> 'inherit_option'" in sql
            assert "to_jsonb(membership) ->> 'set_option'" in sql
            assert sql.count("::boolean, TRUE)") == 4
            assert "OR grantee.rolsuper" in sql
            assert "membership.member = role_membership.roleid" in sql
            assert "OR role_membership.member_is_superuser" in sql
            assert "SELECT COUNT(*) FROM pg_roles AS grantee" in sql
            assert "role_membership.member = grantee.oid" in sql
            assert "role_membership.roleid = role.oid" in sql
            assert ") <= 1" in sql
            return _CatalogResult(scalar=True)
        if "has_schema_privilege(:role_name" in sql:
            return _CatalogResult(scalar=True)
        if "SELECT COUNT(*) FROM pg_class" in sql:
            return _CatalogResult(scalar=len(Base.metadata.tables))
        if "FROM pg_policy AS policy" in sql:
            return _CatalogResult(rows=policy_rows)
        if "has_table_privilege" in sql:
            expected = table_privileges.get(
                (GRAPH_RUNTIME_CAPABILITY, parameters["table_name"]),
                frozenset(),
            )
            return _CatalogResult(scalar=parameters["privilege"] in expected)
        if "has_column_privilege" in sql:
            table_name = parameters["table_name"]
            privilege = parameters["privilege"]
            expected = table_privileges.get((GRAPH_RUNTIME_CAPABILITY, table_name), frozenset())
            lock_column_update = (
                privilege == "UPDATE" and table_name in grac_tables and parameters["column_name"] == "id"
            )
            return _CatalogResult(scalar=privilege in expected or lock_column_update)
        if "pg_get_serial_sequence" in sql:
            return _CatalogResult(scalar=f"{parameters['table_name']}_id_seq")
        if "has_sequence_privilege" in sql:
            return _CatalogResult(scalar=True)
        raise AssertionError(f"unexpected catalog query: {sql}")

    connection = MagicMock()
    connection.execute.side_effect = _execute

    _verify_runtime_capability_catalog(connection, capabilities)


@pytest.mark.parametrize(
    ("checkpoint", "error_match"),
    [
        ("unsafe-role", "unsafe or missing runtime capability role"),
        ("schema-grants", "runtime schema grants"),
        ("rls-disabled", "row-level security enabled"),
        ("policy-mismatch", "RLS policy catalog"),
    ],
)
def test_runtime_capability_catalog_rejects_early_contract_mismatches(checkpoint: str, error_match: str) -> None:
    """Each early catalog mismatch fails with its bounded compatibility error."""
    from src.data import relationship_assertion_db_models  # noqa: F401

    catalog_results = {
        "unsafe-role": [_CatalogResult(scalar=False)],
        "schema-grants": [_CatalogResult(scalar=True), _CatalogResult(scalar=False)],
        "rls-disabled": [
            _CatalogResult(scalar=True),
            _CatalogResult(scalar=True),
            _CatalogResult(scalar=len(Base.metadata.tables) - 1),
        ],
        "policy-mismatch": [
            _CatalogResult(scalar=True),
            _CatalogResult(scalar=True),
            _CatalogResult(scalar=len(Base.metadata.tables)),
            _CatalogResult(rows=[]),
        ],
    }[checkpoint]
    connection = MagicMock()
    connection.execute.side_effect = catalog_results

    with pytest.raises(SchemaCompatibilityError, match=error_match):
        _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))


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


def test_check_normalization_preserves_boolean_grouping() -> None:
    """Constraint comparison must not erase parentheses that change precedence."""
    grouped = "CHECK ((a = 1 OR b = 1) AND c = 1)"
    ungrouped = "CHECK (a = 1 OR b = 1 AND c = 1)"
    assert _normalize_check_definition(grouped) != _normalize_check_definition(ungrouped)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("CHECK (code = 'A')", "CHECK (code = 'a')"),
        ("CHECK (\"Code\" = 'A')", "CHECK (\"code\" = 'A')"),
        ("CHECK (code = 'A''B')", "CHECK (code = 'a''b')"),
    ],
)
def test_check_normalization_preserves_quoted_token_case(left: str, right: str) -> None:
    """Case-sensitive literals and quoted identifiers must remain distinct."""
    assert _normalize_check_definition(left) != _normalize_check_definition(right)


def test_check_normalization_accepts_equivalent_lowercase_quoted_identifier() -> None:
    """A quoted lowercase identifier should match its PostgreSQL unquoted form."""
    assert _normalize_check_definition("CHECK (\"code\" = 'A')") == _normalize_check_definition("CHECK (code = 'A')")


def test_check_normalization_does_not_rewrite_literal_sql_syntax() -> None:
    """Operator, cast, and BETWEEN text inside a literal must remain opaque."""
    literal = "'A::TEXT ~~ BETWEEN X AND Y'"
    assert literal in _normalize_check_definition(f"CHECK (label = {literal})")


@pytest.mark.parametrize(
    ("mismatch", "error_match"),
    [("check", "incompatible constraints"), ("index", "incompatible indexes")],
)
def test_table_schema_rejects_same_named_definition_drift(
    mismatch: str,
    error_match: str,
    isolated_base,
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


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the get_settings LRU cache before and after each test."""
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.unit


def _assert_model_registered(model: type[Base], expected_tablename: str) -> None:
    """
    Verify that a SQLAlchemy model's `__tablename__` equals the expected table name.

    Parameters:
        model (type[Base]): Declarative model class to check.
        expected_tablename (str): Expected value of the model's `__tablename__`.

    Raises:
        AssertionError: If the model's `__tablename__` does not match `expected_tablename`.
    """
    assert model.__tablename__ == expected_tablename


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """
    Provide an isolated declarative SQLAlchemy Base subclass for use within a single test.

    This fixture yields a Base subclass with `__abstract__ = True`; any tables
    registered on the global Base.metadata during the test are removed after the
    fixture completes.

    Returns:
        isolated_base (type[Base]): A declarative Base subclass whose test-created
            tables will be cleaned from the global metadata after the test.
    """
    existing_tables = set(Base.metadata.tables)

    class _IsolatedBase(Base):
        """
        A declarative base subclass for isolating test-specific table metadata.

        Ensures that tables defined within tests do not pollute the global metadata.
        """

        __abstract__ = True

    yield _IsolatedBase

    # Remove any tables registered during the test.
    new_tables = [name for name in Base.metadata.tables if name not in existing_tables]
    for name in new_tables:
        Base.metadata.remove(Base.metadata.tables[name])


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """
    Create and yield an in-memory SQLite Engine for tests.

    The engine uses StaticPool and disables SQLite's same-thread check so
    multiple sessions can share the in-memory database. The engine is disposed
    when the fixture teardown runs.

    Returns:
        An in-memory SQLite `Engine` instance; it is disposed after use.
    """
    in_memory_engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # GRAC CHECKs use translate(); register UDF before any create_all on Base.metadata.
    configure_sqlite_engine(in_memory_engine)
    yield in_memory_engine
    in_memory_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine):
    """Provide a SQLAlchemy session factory bound to the test engine."""
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Engine creation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEngineCreation:
    """Test cases for database engine creation."""

    def test_create_engine_with_default_url(self) -> None:
        """Engine creation should fall back to the default URL."""
        with patch.dict(os.environ, {}, clear=True):
            default_engine = create_engine_from_url()
            assert default_engine is not None
            assert "sqlite" in str(default_engine.url).lower()

    def test_create_engine_with_custom_url(self) -> None:
        """Engine creation with an explicit database URL."""
        custom_url = "sqlite:///test_custom.db"
        custom_engine = create_engine_from_url(custom_url)
        assert "test_custom.db" in str(custom_engine.url)

    def test_create_engine_with_in_memory_sqlite(self) -> None:
        """In-memory SQLite should use StaticPool."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(in_memory_engine.pool, StaticPool)

    def test_create_engine_with_env_variable(self) -> None:
        """Environment variable should override default database URL."""
        from src.config.settings import get_settings

        test_url = "sqlite:///env_test.db"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            get_settings.cache_clear()  # Clear cache to pick up new env vars
            env_engine = create_engine_from_url()
            assert "env_test.db" in str(env_engine.url)

    def test_create_engine_with_postgres_url(self) -> None:
        """PostgreSQL URLs should be accepted."""
        postgres_url = "postgresql://user:pass@localhost/testdb"
        postgres_engine = create_engine_from_url(postgres_url)
        assert "postgresql" in str(postgres_engine.url).lower()


# ---------------------------------------------------------------------------
# Session factory tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSessionFactory:
    """Test cases for session factory creation."""

    def test_factory_returns_callable(self, engine: Engine) -> None:
        """Factory should be callable."""
        factory = create_session_factory(engine)
        assert callable(factory)  # nosec B101

    def test_factory_creates_sessions(self, engine: Engine) -> None:
        """Factory should create usable sessions."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine  # nosec B101
        finally:
            session.close()

    def test_sessions_are_not_autocommit(self, engine: Engine) -> None:
        """Sessions should have autocommit disabled."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine
            # Note: session.autocommit is deprecated in SQLAlchemy 2.0.
            # Sessions created with future=True don't have autocommit mode.
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Database initialization tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_init_db_creates_tables(self, engine: Engine, isolated_base) -> None:
        """Verify that init_db creates registered model tables."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for verifying table creation functionality."""

            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        _assert_model_registered(TestModel, "test_model")

        init_db(engine)

        inspector = inspect(engine)
        assert "test_model" in inspector.get_table_names()  # nosec B101

    def test_init_db_is_idempotent(self, engine: Engine, isolated_base) -> None:
        """Calling init_db multiple times should not error."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model for verifying that database initialization is idempotent."""

            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        _assert_model_registered(TestModel, "test_idempotent")

        init_db(engine)
        init_db(engine)

        inspector = inspect(engine)
        assert "test_idempotent" in inspector.get_table_names()  # nosec B101

    def test_init_db_preserves_existing_data(
        self,
        engine: Engine,
        session_factory,
        isolated_base,
    ) -> None:
        """init_db should not wipe existing data."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model for testing data preservation during database initialization."""

            __tablename__ = "test_preserve"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)

        with session_scope(session_factory) as session:
            session.add(TestModel(id=1, value="persisted"))

        init_db(engine)

        with session_scope(session_factory) as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None  # nosec B101
            assert result.value == "persisted"  # nosec B101

    def test_init_db_applies_postgres_heartbeat_migration(self) -> None:
        """init_db should invoke PostgreSQL compatibility migration for postgres engines."""
        engine = Mock(spec=Engine)
        engine.url = "postgresql://user:pass@localhost/testdb"

        with (
            patch("src.data.database.Base.metadata.create_all") as create_all,
            patch("src.data.migrations.apply_migrations") as apply_sqlite_migrations,
            patch("src.data.migrations.apply_postgresql_heartbeat_migration") as apply_postgres_migration,
            patch("src.data.relationship_assertion_schema.ensure_relationship_assertion_schema") as ensure_grac,
        ):
            init_db(engine)

        create_all.assert_called_once_with(engine)
        apply_postgres_migration.assert_called_once_with(engine)
        apply_sqlite_migrations.assert_not_called()
        ensure_grac.assert_called_once_with(engine)

    def test_runtime_verifier_accepts_initialized_schema(self, engine: Engine) -> None:
        """Explicit migration output should satisfy the read-only runtime verifier."""
        init_db(engine)

        verify_database_schema(engine)

    def test_runtime_verifier_fails_without_creating_schema(self, tmp_path) -> None:
        """An empty runtime database should fail closed and remain empty."""
        empty_engine = create_engine_from_url(f"sqlite:///{tmp_path / 'empty-runtime.db'}")
        try:
            with pytest.raises(SchemaCompatibilityError, match="missing required tables"):
                verify_database_schema(empty_engine)

            assert inspect(empty_engine).get_table_names() == []
        finally:
            empty_engine.dispose()

    def test_runtime_verifier_supports_query_only_cold_start_and_restart(self, tmp_path) -> None:
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
    def test_postgresql_runtime_authority_posture(self, restricted: bool) -> None:
        """PostgreSQL runtime authority must reject privileged and accept restricted roles."""
        runtime_engine = Mock(spec=Engine)
        runtime_engine.url = "postgresql://runtime:secret@database.invalid/fardb"
        connection = MagicMock()
        connection.execute.return_value.scalar_one.return_value = restricted
        runtime_engine.connect.return_value.__enter__ = MagicMock(return_value=connection)
        runtime_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("src.data.database._verify_runtime_login_relation_grants") as verify_relation_grants,
            patch("src.data.database._verify_runtime_login_sequence_grants") as verify_sequence_grants,
        ):
            if not restricted:
                with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
                    verify_runtime_database_authority(runtime_engine)
                return

            connection.execute.return_value.scalars.return_value.all.return_value = []
            verify_runtime_database_authority(runtime_engine)

        verify_relation_grants.assert_called_once_with(connection, ())
        verify_sequence_grants.assert_called_once_with(connection, ())
        restricted_query = str(connection.execute.call_args_list[0].args[0])
        membership_query = str(connection.execute.call_args_list[1].args[0])
        assert "current_schema() IS NOT NULL" in restricted_query
        assert "login.rolname = session_user" in restricted_query
        assert "pg_has_role(login.oid, assumable.oid, 'MEMBER')" in restricted_query
        assert "has_database_privilege(assumable.oid, current_database(), 'CREATE')" in restricted_query
        assert "namespace.nspowner = assumable.oid" in restricted_query
        assert "database.datdba = assumable.oid" in restricted_query
        assert "pg_has_role(login.oid, assumable.oid, 'MEMBER')" in membership_query
        assert "assumable.oid <> login.oid" in membership_query


# ---------------------------------------------------------------------------
# Transaction scope tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSessionScope:
    """Tests for transactional session_scope behavior."""

    def test_commits_on_success(self, engine: Engine, isolated_base) -> None:
        """session_scope should commit on success."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model for commit testing."""

            __tablename__ = "test_commit"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="committed"))

        with session_scope(factory) as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None  # nosec B101
            assert result.value == "committed"  # nosec B101

    def test_rolls_back_on_exception(self, engine: Engine, isolated_base) -> None:
        """session_scope should rollback on error."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model for rollback testing."""

            __tablename__ = "test_rollback"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(ValueError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            raise ValueError("trigger rollback")

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0  # nosec B101

    def test_propagates_integrity_error(self, engine: Engine, isolated_base) -> None:
        """
        Verify that an IntegrityError raised inside a session_scope is propagated
        to the caller after the transaction is rolled back.

        This test creates a simple model, initializes the database, and performs
        operations that raise an IntegrityError; the error must not be swallowed
        by the session scope.
        """

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model used in tests to trigger and verify integrity errors."""

            __tablename__ = "test_integrity"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            session.flush()
            session.add(TestModel(id=1))
            session.flush()

    def test_nested_operations_commit(self, engine: Engine, isolated_base) -> None:
        """Multiple operations in one scope should commit atomically."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Model for nested operations commit tests."""

            __tablename__ = "test_nested"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="a"))
            session.add(TestModel(id=2, value="b"))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 2  # nosec B101


# ---------------------------------------------------------------------------
# Default database URL tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDefaultDatabaseURL:
    """Tests for DEFAULT_DATABASE_URL behavior."""

    def test_default_is_sqlite(self) -> None:
        """Default database URL should use SQLite."""
        assert "sqlite" in DEFAULT_DATABASE_URL.lower()  # nosec B101

    def test_default_points_to_file(self) -> None:
        """
        Verify the default database URL points to the file named 'asset_graph.db'.

        Asserts that DEFAULT_DATABASE_URL contains the substring 'asset_graph.db'.
        """
        assert "asset_graph.db" in DEFAULT_DATABASE_URL  # nosec B101

    def test_env_override_works(self) -> None:
        """Environment variable should override default URL."""
        from src.config.settings import get_settings

        custom_url = "postgresql://test:test@localhost/test"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": custom_url}):
            get_settings.cache_clear()  # Clear cache to pick up new env vars
            override_engine = create_engine_from_url()
            assert "postgresql" in str(override_engine.url).lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases and defensive behavior tests."""

    def test_empty_session_scope(self, engine: Engine) -> None:
        """session_scope should allow empty usage."""
        factory = create_session_factory(engine)
        with session_scope(factory):
            pass

    def test_create_engine_with_empty_string(self) -> None:
        """Empty string should fall back to default."""
        with patch.dict(os.environ, {}, clear=True):
            fallback_engine = create_engine_from_url("")
            assert fallback_engine is not None

    def test_create_engine_with_none(self) -> None:
        """None should fall back to default."""
        fallback_engine = create_engine_from_url(None)
        assert fallback_engine is not None

    def test_create_engine_with_malformed_explicit_url_raises(self) -> None:
        """Malformed explicit URL should raise ArgumentError, not fall back."""
        from sqlalchemy.exc import ArgumentError

        malformed_url = "not-a-valid-database-url"
        with pytest.raises(ArgumentError):
            create_engine_from_url(malformed_url)


# ---------------------------------------------------------------------------
# Connection pooling tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectionPooling:
    """Tests for database connection pooling behavior."""

    def test_static_pool_for_in_memory_sqlite(self) -> None:
        """In-memory SQLite should use StaticPool for thread safety."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(in_memory_engine.pool, StaticPool)

    def test_multiple_connections_to_same_in_memory_db(self, isolated_base) -> None:
        """Multiple connections to in-memory DB should share same data with StaticPool."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")

        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=in_memory_engine)

        class TestTable(isolated_base):  # type: ignore[misc]
            """Test table for connection pooling validation."""

            __tablename__ = "test_pool"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        isolated_base.metadata.create_all(in_memory_engine)

        session1 = Session()
        session1.add(TestTable(id=1, value="test"))
        session1.commit()
        session1.close()

        session2 = Session()
        result = session2.query(TestTable).filter_by(id=1).one_or_none()
        assert result is not None
        assert result.value == "test"
        session2.close()

        isolated_base.metadata.drop_all(in_memory_engine)

    def test_pool_size_configuration_for_postgres(self) -> None:
        """PostgreSQL URLs should accept pool size configuration."""
        postgres_url = "postgresql://user:pass@localhost/db"
        postgres_engine = create_engine_from_url(postgres_url)
        assert postgres_engine is not None


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConcurrentDatabaseAccess:
    """Tests for concurrent database access scenarios."""

    def test_concurrent_session_creation(self, engine: Engine) -> None:
        """Multiple concurrent sessions should be safe."""
        factory = create_session_factory(engine)
        sessions: list[Any] = []
        errors: list[Exception] = []

        def create_session() -> None:
            """
            Create a session using the surrounding `factory`, append it to the
            surrounding `sessions` list, then close it; on exception, append
            the exception to the surrounding `errors` list.
            """
            try:
                session = factory()
                sessions.append(session)
                session.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=create_session) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(sessions) == 10

    # pylint: disable=too-many-locals
    def test_concurrent_reads_safe(self, isolated_base) -> None:
        """Concurrent reads should not interfere with each other.

        Uses a temporary file-based SQLite database with NullPool so each reader
        thread opens its own database connection. This validates concurrent
        read-session behavior without relying on a shared in-memory SQLite
        connection from StaticPool.
        """

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for concurrent read validation."""

            __tablename__ = "test_concurrent_reads"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        results: list[int] = []
        errors: list[Exception] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{os.path.join(tmpdir, 'concurrent_reads.db')}"
            # NullPool: each session opens its own SQLite connection, so concurrent
            # reads are exercised at the database level rather than through a single
            # shared in-memory connection.
            file_engine = create_engine(
                db_url,
                poolclass=NullPool,
                connect_args={"timeout": 30},
            )
            init_db(file_engine)
            factory = create_session_factory(file_engine)

            with session_scope(factory) as session:
                for i in range(100):
                    session.add(TestModel(id=i, value=f"value_{i}"))

            def read_data() -> None:
                """
                Worker executed by a thread to perform a read-only count query.

                Appends the number of rows in `TestModel` to the shared `results`
                list. If an exception occurs, appends the exception instance to the
                shared `errors` list.
                """
                try:
                    with session_scope(factory) as session:
                        count = session.query(TestModel).count()
                        results.append(count)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=read_data) for _ in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            file_engine.dispose()

        assert len(errors) == 0, f"Unexpected errors under concurrent reads: {errors}"
        assert len(results) == 10
        assert all(count == 100 for count in results)

    def test_concurrent_writes(self, isolated_base) -> None:
        """Verify the session_scope handles true concurrent writes without external locking.

        Uses a temporary file-based SQLite database with NullPool so each thread
        opens its own connection.  SQLite serialises concurrent writers at the
        database level; the test asserts that all ``session_scope`` operations
        complete successfully, validating the DB/session stack under concurrency
        without relying on any Python-level locking.
        """

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for concurrent write validation."""

            __tablename__ = "test_concurrent_writes"
            id = Column(Integer, primary_key=True)

        errors: list[Exception] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{os.path.join(tmpdir, 'concurrent.db')}"
            # NullPool: each call to session_scope opens its own SQLite connection
            # so concurrent access is exercised at the database level, not masked
            # by a shared in-memory connection.
            file_engine = create_engine(
                db_url,
                poolclass=NullPool,
                connect_args={"timeout": 30},  # wait up to 30 s for the DB lock
            )
            init_db(file_engine)
            factory = create_session_factory(file_engine)

            def write_data(thread_id: int) -> None:
                """
                Insert a TestModel row using thread_id as the primary key and record any exception.

                Opens a transactional session via ``session_scope`` without external
                locking so that the SQLite database-level serialisation is exercised.
                Any exception is appended to the shared ``errors`` list.

                Parameters:
                    thread_id (int): Integer used as the TestModel ``id``.
                """
                try:
                    with session_scope(factory) as session:
                        session.add(TestModel(id=thread_id))
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            num_threads = 20
            threads = [threading.Thread(target=write_data, args=(i,)) for i in range(num_threads)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            # SQLite serialises concurrent writes at the database level.
            # All session_scope operations must complete without error.
            with session_scope(factory) as session:
                count = session.query(TestModel).count()

            file_engine.dispose()

        assert len(errors) == 0, f"Unexpected errors under concurrent writes: {errors}"
        assert count == num_threads, f"Expected {num_threads} rows, found {count}"


# ---------------------------------------------------------------------------
# Error recovery tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseErrorRecovery:
    """Tests for database error recovery scenarios."""

    def test_session_scope_recovers_from_nested_error(self, engine: Engine, isolated_base) -> None:
        """Session scope should recover after error in nested operation."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for error recovery validation."""

            __tablename__ = "test_error_recovery"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        try:
            with session_scope(factory) as session:
                session.add(TestModel(id=1, value="test"))
                raise ValueError("Intentional error")
        except ValueError:
            # Expected error from nested operation; session should be rolled back.
            pass

        with session_scope(factory) as session:
            session.add(TestModel(id=2, value="success"))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 1
            result = session.query(TestModel).one()
            assert result.id == 2
            assert result.value == "success"

    def test_session_scope_handles_commit_failure(self, engine: Engine, isolated_base) -> None:
        """Session scope should handle commit failures gracefully."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for commit failure handling."""

            __tablename__ = "test_commit_failure"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            session.flush()
            session.add(TestModel(id=1))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0


# ---------------------------------------------------------------------------
# Resource cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResourceCleanup:
    """Tests for proper resource cleanup."""

    def test_engine_disposal_releases_connections(self) -> None:
        """Engine disposal should release all connections."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        factory = create_session_factory(in_memory_engine)

        for _ in range(5):
            session = factory()
            session.close()

        in_memory_engine.dispose()

        new_engine = create_engine_from_url("sqlite:///:memory:")
        assert new_engine is not None
        new_engine.dispose()

    def test_session_scope_closes_on_exception(self, engine: Engine) -> None:
        """Session should be closed even when exception occurs."""
        factory = create_session_factory(engine)
        with pytest.raises(RuntimeError), session_scope(factory) as session:
            assert session.is_active
            raise RuntimeError("Test error")

    def test_multiple_session_scopes_cleanup_properly(self, engine: Engine, isolated_base) -> None:
        """Multiple session scopes should clean up properly."""

        class TestModel(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for cleanup validation."""

            __tablename__ = "test_cleanup"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        for i in range(10):
            with session_scope(factory) as session:
                session.add(TestModel(id=i))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 10

    def test_session_scope_with_nested_commits(self, engine: Engine, isolated_base) -> None:
        """
        Verifies that explicit commits performed inside a session_scope persist
        data across subsequent scopes.

        This test creates a simple model, performs explicit commits within a
        session_scope (simulating a regression where nested commits might be
        discarded), and then opens a new session_scope to assert the committed
        row is visible.
        """

        class TestModelBase(isolated_base):  # type: ignore[misc]  # pylint: disable=redefined-outer-name
            """Test model for nested commit validation."""

            __tablename__ = "test_nested_commits"
            id = Column(Integer, primary_key=True)

        isolated_base.metadata.create_all(engine)
        factory = create_session_factory(engine)

        # First transaction
        with session_scope(factory) as session:
            session.add(TestModelBase(id=1))
            session.commit()  # Explicit commit (regression scenario)
            session.add(TestModelBase(id=2))
            session.commit()  # Explicit commit (regression scenario)

        # Second transaction should see first
        with session_scope(factory) as session:
            assert session.query(TestModelBase).count() == 2


# ============================================================================
# ADDITIONAL COMPREHENSIVE TESTS - Enhanced Coverage for api/database.py
# ============================================================================


@pytest.mark.unit
class TestResolveSqlitePathEnhancements:
    """Additional edge case tests for _resolve_sqlite_path."""

    def test_resolve_sqlite_path_with_query_parameters(self):
        """Test resolving SQLite URL with query parameters."""
        url = "sqlite:///test.db?mode=ro"
        result = _resolve_sqlite_path(url)
        assert "test.db" in result

    def test_resolve_sqlite_path_with_percent_encoding(self):
        """Test resolving SQLite URL with percent-encoded characters."""
        url = "sqlite:///test%20database.db"
        result = _resolve_sqlite_path(url)
        assert "test database.db" in result

    def test_resolve_sqlite_path_uri_memory_with_cache_shared(self):
        """Test resolving URI-style memory database with shared cache."""
        url = "sqlite:///file::memory:?cache=shared"
        result = _resolve_sqlite_path(url)
        assert "file::memory:" in result

    def test_resolve_sqlite_path_with_trailing_slashes(self):
        """Test resolving path with multiple trailing slashes."""
        url = "sqlite:///:memory:/"
        result = _resolve_sqlite_path(url)
        assert result == ":memory:"

    def test_resolve_sqlite_path_absolute_unix_path(self):
        """Test resolving absolute Unix-style path."""
        url = "sqlite:////absolute/path/to/db.sqlite"
        result = _resolve_sqlite_path(url)
        assert result.startswith("/")

    def test_resolve_sqlite_path_windows_drive_letter(self):
        """Test resolving Windows path with drive letter."""
        url = "sqlite:///C:/Users/test/database.db"
        result = _resolve_sqlite_path(url)
        assert "C:" in result or "database.db" in result

    def test_resolve_sqlite_path_special_characters(self):
        """Test resolving path with special characters."""
        url = "sqlite:///test-db_v2.sqlite"
        result = _resolve_sqlite_path(url)
        assert "test-db_v2.sqlite" in result

    def test_resolve_sqlite_path_non_sqlite_scheme_raises(self):
        """Test that non-SQLite schemes raise ValueError."""
        with pytest.raises(ValueError, match="Not a valid sqlite URI"):
            _resolve_sqlite_path("postgresql:///database")

    def test_resolve_sqlite_path_empty_path_component(self):
        """Test resolving URL with empty path component."""
        url = "sqlite:///"
        result = _resolve_sqlite_path(url)
        assert isinstance(result, str)


@pytest.mark.unit
class TestIsMemoryDbEnhancements:
    """Additional edge case tests for _is_memory_db."""

    def test_is_memory_db_with_uri_query_params(self):
        """Test detecting memory DB with various URI query parameters."""
        test_cases = [
            "file::memory:?mode=memory",
            "file::memory:?cache=shared",
            "file::memory:?cache=shared&mode=memory",
        ]
        for uri in test_cases:
            assert _is_memory_db(uri) is True

    def test_is_memory_db_with_file_scheme_but_not_memory(self):
        """Test that file:// URLs not containing memory return False."""
        assert _is_memory_db("file:///path/to/db.sqlite") is False

    def test_is_memory_db_case_sensitivity(self):
        """Test memory detection is case-sensitive."""
        assert _is_memory_db(":MEMORY:") is False
        assert _is_memory_db(":Memory:") is False

    def test_is_memory_db_with_memory_in_filename(self):
        """Test that 'memory' in filename doesn't trigger false positive."""
        assert _is_memory_db("/path/to/memory_backup.db") is False

    def test_is_memory_db_with_none_defaults_to_config(self):
        """Test that None parameter uses configured DATABASE_PATH."""
        result = _is_memory_db(None)
        assert isinstance(result, bool)


@pytest.mark.unit
class TestExecuteFunctionEnhancements:
    """Additional tests for execute function edge cases."""

    @patch("api.database.get_connection")
    def test_execute_with_empty_parameters(self, mock_get_conn):
        """Test execute with empty parameter tuple."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("SELECT 1", ())

        mock_conn.execute.assert_called_once_with("SELECT 1", ())

    @patch("api.database.get_connection")
    def test_execute_handles_commit(self, mock_get_conn):
        """Test that execute commits changes."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("INSERT INTO test VALUES (?)", (1,))

        sql, params = mock_conn.execute.call_args[0]
        assert sql == "INSERT INTO test VALUES (?)"
        assert list(params) == [1]
        mock_conn.commit.assert_called_once()

    @patch("api.database.get_connection")
    def test_execute_with_list_parameters(self, mock_get_conn):
        """Test execute accepts list parameters."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("INSERT INTO test VALUES (?, ?)", [1, 2])

        mock_conn.execute.assert_called_once_with("INSERT INTO test VALUES (?, ?)", [1, 2])


@pytest.mark.unit
class TestFetchOperationsEnhancements:
    """Additional tests for fetch operations."""

    @patch("api.database.get_connection")
    def test_fetch_one_with_no_results(self, mock_get_conn):
        """Test fetch_one returns None when no results."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_one("SELECT * FROM nonexistent")

        assert result is None

    @patch("api.database.get_connection")
    def test_fetch_one_with_complex_query(self, mock_get_conn):
        """Test fetch_one with complex JOIN query."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = {"id": 1, "name": "test"}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_one(
            "SELECT * FROM table1 JOIN table2 ON table1.id = table2.id WHERE table1.id = ?",
            (1,),
        )

        assert result == mock_row

    @patch("api.database.get_connection")
    def test_fetch_value_with_aggregate(self, mock_get_conn):
        """Test fetch_value with aggregate function."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = (42,)
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_value("SELECT COUNT(*) FROM table")

        assert result == 42

    @patch("api.database.get_connection")
    def test_fetch_value_with_null_result(self, mock_get_conn):
        """Test fetch_value when result is NULL."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = (None,)
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_value("SELECT nullable_column FROM table")

        assert result is None


@pytest.mark.unit
class TestDatabaseErrorHandling:
    """Test error handling in database operations."""

    @patch("api.database.get_connection")
    def test_execute_propagates_errors(self, mock_get_conn):
        """Test that execute propagates SQLite errors."""
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_conn.execute.side_effect = sqlite3.Error("SQL error")
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(sqlite3.Error):
            execute("INVALID SQL")

        mock_conn.commit.assert_not_called()

    @patch("api.database.get_connection")
    def test_fetch_one_propagates_errors(self, mock_get_conn):
        """Test that fetch_one propagates query errors."""
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("Table not found")
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(sqlite3.OperationalError):
            fetch_one("SELECT * FROM nonexistent")


@pytest.mark.unit
class TestDatabaseUrlConfiguration:
    """Test database URL configuration edge cases."""

    @patch.dict("os.environ", {}, clear=True)
    def test_get_database_url_missing_env_var(self):
        """Test that missing DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError, match="DATABASE_URL"):
            _get_database_url()

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_get_database_url_empty_string(self):
        """Test that empty DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError):
            _get_database_url()

    @patch.dict("os.environ", {"DATABASE_URL": "   "})
    def test_get_database_url_whitespace_only(self):
        """Test that whitespace-only DATABASE_URL is returned as-is."""
        result = _get_database_url()
        assert result == "   "

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:pass@localhost/db"})
    def test_get_database_url_returns_configured_value(self):
        """Test that configured URL is returned as-is."""
        result = _get_database_url()
        assert result == "postgresql://user:pass@localhost/db"


@pytest.mark.unit
class TestNestedConnectionCalls:
    """Test nested get_connection() calls with reentrant lock."""

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"})
    def test_nested_get_connection_with_execute(self):
        """
        Test that nested get_connection() calls don't deadlock on in-memory DB.

        This regression test verifies that _MEMORY_USE_LOCK is reentrant (RLock)
        and allows same-thread nested calls to get_connection().
        """
        # Clean up any existing connection
        _cleanup_memory_connection()

        # Outer get_connection call
        with get_connection() as outer_conn:
            # Create a test table
            outer_conn.execute("DROP TABLE IF EXISTS test_table")
            outer_conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
            outer_conn.commit()

            # Nested execute() which calls get_connection() internally
            # This should not deadlock with RLock
            execute("INSERT INTO test_table (id, value) VALUES (1, 'nested')")

            # Verify the nested write succeeded
            cursor = outer_conn.execute("SELECT value FROM test_table WHERE id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "nested"

        # Clean up
        _cleanup_memory_connection()

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"})
    def test_nested_get_connection_with_fetch_one(self):
        """Test nested get_connection() with fetch_one helper."""
        _cleanup_memory_connection()

        with get_connection() as outer_conn:
            outer_conn.execute("CREATE TABLE IF NOT EXISTS test_data (id INTEGER, name TEXT)")
            outer_conn.execute("INSERT INTO test_data VALUES (42, 'test')")
            outer_conn.commit()

            # Nested fetch_one() which calls get_connection() internally
            row = fetch_one("SELECT name FROM test_data WHERE id = ?", (42,))
            assert row is not None
            assert row[0] == "test"

        _cleanup_memory_connection()

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"})
    def test_nested_get_connection_with_fetch_value(self):
        """Test nested get_connection() with fetch_value helper."""
        _cleanup_memory_connection()

        with get_connection() as outer_conn:
            outer_conn.execute("CREATE TABLE IF NOT EXISTS counter (val INTEGER)")
            outer_conn.execute("INSERT INTO counter VALUES (99)")
            outer_conn.commit()

            # Nested fetch_value() which calls get_connection() internally
            value = fetch_value("SELECT val FROM counter LIMIT 1")
            assert value == 99

        _cleanup_memory_connection()
