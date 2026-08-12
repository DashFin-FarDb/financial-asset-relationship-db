"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
    bindparam,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.settings import get_settings

from .base import Base
from .check_constraint_normalization import normalize_check_definition as _normalize_check_definition

# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402
from .runtime_role_membership import USABLE_ROLE_MEMBERSHIP_CTE_SQL

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"
ASSET_GRAPH_DATABASE_URL_ENV_VAR = "ASSET_GRAPH_DATABASE_URL"
SQLITE_MEMORY_DATABASE = ":memory:"

GRAPH_RUNTIME_CAPABILITY = "graph"
COORDINATION_RUNTIME_CAPABILITY = "coordination"
GRAPH_RUNTIME_ROLE = "fardb_runtime_graph"
COORDINATION_RUNTIME_ROLE = "fardb_runtime_coordination"
RUNTIME_CAPABILITY_ROLES = {
    GRAPH_RUNTIME_CAPABILITY: GRAPH_RUNTIME_ROLE,
    COORDINATION_RUNTIME_CAPABILITY: COORDINATION_RUNTIME_ROLE,
}

_GRAPH_MUTABLE_TABLES = (
    "assets",
    "asset_relationships",
    "regulatory_events",
    "regulatory_event_assets",
)
_GRAPH_JOB_TABLE = "rebuild_jobs"
_COORDINATION_TABLE = "distributed_locks"
_GRAPH_SEQUENCE_TABLE_COLUMNS = (
    ("asset_relationships", "id"),
    ("regulatory_event_assets", "id"),
)
_RLS_COMMANDS = {
    "SELECT": "r",
    "INSERT": "a",
    "UPDATE": "w",
    "DELETE": "d",
}
_RLS_COMMAND_NAMES = {code: name for name, code in _RLS_COMMANDS.items()}
_TABLE_PRIVILEGES = (*_RLS_COMMANDS, "TRUNCATE", "REFERENCES", "TRIGGER")
_COLUMN_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
_SEQUENCE_PRIVILEGES = ("USAGE", "SELECT", "UPDATE")
_GRAPH_SEQUENCE_PRIVILEGES = frozenset({"USAGE", "SELECT"})


class SchemaCompatibilityError(RuntimeError):
    """Raised when a runtime database does not match the required schema contract."""


class CapabilityRoleBootstrapRequiredError(SchemaCompatibilityError):
    """Raised when a non-superuser migration owner finds a missing capability role."""

    def __init__(self, role_name: str) -> None:
        """Build the fixed operator diagnostic for one missing capability role."""
        super().__init__(
            f"required PostgreSQL capability role {role_name} is missing; run "
            "scripts/bootstrap_database_capability_roles.sql as a PostgreSQL superuser "
            "before the normal database migration"
        )


def _sqlite_translate(value: str | None, from_chars: str | None, to_chars: str | None) -> str | None:
    """PostgreSQL-compatible ``translate`` for SQLite CHECK constraints."""
    if value is None:
        return None
    if from_chars is None:
        return None
    if to_chars is None:
        return None
    mapped: dict[str, str | None] = {}
    for index, char in enumerate(from_chars):
        if index < len(to_chars):
            mapped[char] = to_chars[index]
        else:
            mapped[char] = None
    pieces: list[str] = []
    for char in value:
        if char not in mapped:
            pieces.append(char)
            continue
        replacement = mapped[char]
        if replacement is None:
            continue
        pieces.append(replacement)
    return "".join(pieces)


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement and Postgres-compatible helpers on SQLite connects."""
    dbapi_connection.create_function("translate", 3, _sqlite_translate)
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_sqlite_engine(engine: Engine) -> Engine:
    """Attach SQLite connection hooks required for GRAC FK + CHECK integrity.

    Registers a Postgres-compatible ``translate`` UDF and enables
    ``PRAGMA foreign_keys=ON`` on every new DB-API connection. File-backed
    engines dispose pooled connections so the next checkout picks up the hooks;
    in-memory engines configure the live connection in place so StaticPool
    state is preserved.
    """
    if event.contains(engine, "connect", _configure_sqlite_connection):
        return engine
    event.listen(engine, "connect", _configure_sqlite_connection)

    url = make_url(str(engine.url))
    database = url.database or ""
    query: dict = dict(url.query) if getattr(url, "query", None) else {}
    is_memory = database == SQLITE_MEMORY_DATABASE or query.get("mode") == "memory"
    if is_memory:
        with engine.connect() as connection:
            dbapi_connection = connection.connection.dbapi_connection
            _configure_sqlite_connection(dbapi_connection, None)
    else:
        engine.dispose()
    return engine


# Backward-compatible private alias.
_configure_sqlite_engine = configure_sqlite_engine


def create_engine_from_url(url: str | None = None) -> Engine:
    """
    Resolve a database URL and create a SQLAlchemy Engine for the asset store.

    If ``url`` is None, reads ``settings.asset_graph_database_url`` and falls
    back to ``DEFAULT_DATABASE_URL`` when unset. An empty string forces the
    default file-based SQLite URL; otherwise the provided ``url`` is used.

    For SQLite in-memory databases (``database == SQLITE_MEMORY_DATABASE`` or
    query ``mode=memory``), the engine uses ``check_same_thread=False`` and
    ``StaticPool``.

    Parameters:
        url: Optional database URL. None uses settings; empty string uses the
            default file-based SQLite URL.

    Returns:
        Engine configured for the resolved URL, including SQLite in-memory
        connection arguments and a static pool when applicable.

    Raises:
        ArgumentError: If an explicit ``url`` cannot be parsed as a SQLAlchemy URL.
    """
    is_explicit_url = url is not None and url != ""
    if url is None:
        settings = get_settings()
        resolved_url = settings.asset_graph_database_url or DEFAULT_DATABASE_URL
    elif url == "":
        resolved_url = DEFAULT_DATABASE_URL
    else:
        resolved_url = url

    try:
        parsed_url = make_url(resolved_url)
    except ArgumentError:
        if is_explicit_url:
            raise
        return _configure_sqlite_engine(create_engine(DEFAULT_DATABASE_URL, future=True))

    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    database = parsed_url.database or ""
    query: dict = dict(parsed_url.query) if getattr(parsed_url, "query", None) else {}

    is_sqlite_memory = is_sqlite and (database == SQLITE_MEMORY_DATABASE or query.get("mode") == "memory")

    if is_sqlite:
        connect_args = {"check_same_thread": False}
        if is_sqlite_memory:
            return _configure_sqlite_engine(
                create_engine(
                    resolved_url,
                    future=True,
                    connect_args=connect_args,
                    poolclass=StaticPool,
                )
            )
        return _configure_sqlite_engine(
            create_engine(
                resolved_url,
                future=True,
                connect_args=connect_args,
            )
        )

    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy session factory bound to the provided engine.

    Produced sessions use autocommit disabled, autoflush disabled, and
    SQLAlchemy 2.0 ``future`` behavior.

    Parameters:
        engine: Engine to bind produced Session instances to.

    Returns:
        A sessionmaker that produces Session objects bound to ``engine``.
    """
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )


def init_db(engine: Engine) -> None:
    """
    Create database tables for all ORM models declared on Base.metadata.

    Creates any missing tables in the database referenced by the provided SQLAlchemy Engine.
    Also applies any pending SQL migrations to ensure schema is up-to-date, then installs
    GRAC v1 assertion immutability guards.

    Parameters:
        engine (Engine): SQLAlchemy Engine connected to the target database where tables will be created.
    """
    # Register GRAC ORM tables on Base.metadata before create_all.
    from . import relationship_assertion_db_models as _relationship_assertion_db_models  # noqa: F401
    from .migrations import apply_migrations, apply_postgresql_heartbeat_migration
    from .relationship_assertion_schema import ensure_relationship_assertion_schema

    # Apply SQL migrations (e.g., adding heartbeat columns to rebuild_jobs)
    # Extract database path from engine URL for SQLite databases
    # For non-SQLite or in-memory databases, skip migrations (they use create_all only)
    url = make_url(engine.url)
    backend = url.get_backend_name()
    query: dict = dict(url.query) if getattr(url, "query", None) else {}
    is_sqlite_memory = backend == "sqlite" and (url.database == SQLITE_MEMORY_DATABASE or query.get("mode") == "memory")

    # GRAC CHECKs use translate(); attach UDF + FK pragma before create_all.
    if backend == "sqlite":
        configure_sqlite_engine(engine)

    Base.metadata.create_all(engine)

    if backend == "sqlite" and url.database and not is_sqlite_memory:
        apply_migrations(url.database)
    elif backend == "postgresql":
        apply_postgresql_heartbeat_migration(engine)

    ensure_relationship_assertion_schema(engine)


def _verify_table_constraints(inspector, table_name: str, expected_table) -> None:
    """Verify key and uniqueness invariants for one reflected table."""
    expected_primary_key = tuple(column.name for column in expected_table.primary_key.columns)
    actual_primary_key = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
    if expected_primary_key != actual_primary_key:
        raise SchemaCompatibilityError(f"database table {table_name} missing primary-key invariant")

    expected_unique = {
        frozenset(column.name for column in constraint.columns)
        for constraint in expected_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    actual_unique = {
        frozenset(constraint.get("column_names") or ()) for constraint in inspector.get_unique_constraints(table_name)
    }
    if expected_unique - actual_unique:
        raise SchemaCompatibilityError(f"database table {table_name} missing uniqueness invariants")

    expected_foreign_keys = {
        (
            tuple(column.name for column in constraint.columns),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
        )
        for constraint in expected_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    actual_foreign_keys = {
        (
            tuple(constraint.get("constrained_columns") or ()),
            constraint.get("referred_table"),
            tuple(constraint.get("referred_columns") or ()),
        )
        for constraint in inspector.get_foreign_keys(table_name)
    }
    if expected_foreign_keys - actual_foreign_keys:
        raise SchemaCompatibilityError(f"database table {table_name} missing foreign-key invariants")


def _verify_table_checks(inspector, table_name: str, expected_table) -> None:
    """Verify named CHECK constraints for one ORM table."""
    expected_checks = {
        str(constraint.name): _normalize_check_definition(constraint.sqltext)
        for constraint in expected_table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }
    actual_checks = {
        str(constraint["name"]): _normalize_check_definition(constraint.get("sqltext"))
        for constraint in inspector.get_check_constraints(table_name)
        if constraint.get("name")
    }
    missing_checks = sorted(set(expected_checks) - set(actual_checks))
    if missing_checks:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required constraints: {', '.join(missing_checks)}"
        )
    mismatched_checks = sorted(
        name for name, definition in expected_checks.items() if actual_checks[name] != definition
    )
    if mismatched_checks:
        raise SchemaCompatibilityError(
            f"database table {table_name} has incompatible constraints: {', '.join(mismatched_checks)}"
        )


def _expected_table_indexes(expected_table) -> dict[str, tuple[tuple[str, ...], bool]]:
    """Return named ORM index definitions."""
    return {
        str(index.name): (tuple(column.name for column in index.columns), bool(index.unique))
        for index in expected_table.indexes
        if index.name
    }


def _reflected_table_indexes(inspector, table_name: str) -> dict[str, tuple[tuple[str, ...], bool]]:
    """Return named reflected index definitions."""
    return {
        str(index["name"]): (tuple(index.get("column_names") or ()), bool(index.get("unique")))
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def _verify_table_indexes(inspector, table_name: str, expected_table) -> None:
    """Verify named indexes for one ORM table."""
    expected_indexes = _expected_table_indexes(expected_table)
    actual_indexes = _reflected_table_indexes(inspector, table_name)
    missing_indexes = sorted(set(expected_indexes) - set(actual_indexes))
    if missing_indexes:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required indexes: {', '.join(missing_indexes)}"
        )
    mismatched_indexes = sorted(
        name for name, definition in expected_indexes.items() if actual_indexes[name] != definition
    )
    if mismatched_indexes:
        raise SchemaCompatibilityError(
            f"database table {table_name} has incompatible indexes: {', '.join(mismatched_indexes)}"
        )


def _verify_table_schema(inspector, table_name: str) -> None:
    """Verify columns and named schema invariants for one ORM table."""
    expected_table = Base.metadata.tables[table_name]
    actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
    missing_columns = sorted(set(expected_table.columns.keys()) - actual_columns)
    if missing_columns:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required columns: {', '.join(missing_columns)}"
        )

    _verify_table_checks(inspector, table_name, expected_table)
    _verify_table_indexes(inspector, table_name, expected_table)
    _verify_table_constraints(inspector, table_name, expected_table)


def _normalized_runtime_capabilities(capabilities: tuple[str, ...] | set[str] | frozenset[str]) -> tuple[str, ...]:
    """Validate and order repository-owned runtime capability names."""
    unknown = sorted(set(capabilities) - set(RUNTIME_CAPABILITY_ROLES))
    if unknown:
        raise ValueError(f"unknown runtime database capabilities: {', '.join(unknown)}")
    return tuple(capability for capability in RUNTIME_CAPABILITY_ROLES if capability in capabilities)


def _runtime_table_privileges(capabilities: tuple[str, ...]) -> dict[tuple[str, str], frozenset[str]]:
    """Return exact table privileges keyed by capability and table."""
    from .relationship_assertion_db_models import GRAC_TABLE_NAMES

    privileges: dict[tuple[str, str], frozenset[str]] = {}
    if GRAPH_RUNTIME_CAPABILITY in capabilities:
        for table_name in _GRAPH_MUTABLE_TABLES:
            privileges[(GRAPH_RUNTIME_CAPABILITY, table_name)] = frozenset(_RLS_COMMANDS)
        privileges[(GRAPH_RUNTIME_CAPABILITY, _GRAPH_JOB_TABLE)] = frozenset({"SELECT", "INSERT", "UPDATE"})
        for table_name in GRAC_TABLE_NAMES:
            privileges[(GRAPH_RUNTIME_CAPABILITY, table_name)] = frozenset({"SELECT", "INSERT"})
    if COORDINATION_RUNTIME_CAPABILITY in capabilities:
        privileges[(COORDINATION_RUNTIME_CAPABILITY, _COORDINATION_TABLE)] = frozenset(_RLS_COMMANDS)
    return privileges


def _runtime_policy_specs(
    capabilities: tuple[str, ...],
) -> dict[tuple[str, str], tuple[str, str | None, str | None]]:
    """Return exact policy contracts as command, USING, and WITH CHECK expressions."""
    from .relationship_assertion_db_models import GRAC_TABLE_NAMES

    specs: dict[tuple[str, str], tuple[str, str | None, str | None]] = {}
    for (capability, table_name), privileges in _runtime_table_privileges(capabilities).items():
        for command in _RLS_COMMANDS:
            if command not in privileges:
                continue
            policy_name = f"fardb_{capability}_{command.lower()}_v1"
            if command == "SELECT":
                specs[(table_name, policy_name)] = (_RLS_COMMANDS[command], "true", None)
            elif command == "INSERT":
                specs[(table_name, policy_name)] = (_RLS_COMMANDS[command], None, "true")
            elif command == "UPDATE":
                specs[(table_name, policy_name)] = (_RLS_COMMANDS[command], "true", "true")
            else:
                specs[(table_name, policy_name)] = (_RLS_COMMANDS[command], "true", None)
        if capability == GRAPH_RUNTIME_CAPABILITY and table_name in GRAC_TABLE_NAMES:
            # PostgreSQL requires UPDATE authority and an UPDATE policy for
            # SELECT ... FOR UPDATE. Only the immutable primary-key column is
            # granted, while WITH CHECK (false) makes actual writes unusable.
            specs[(table_name, "fardb_graph_lock_v1")] = ("w", "true", "false")
    return specs


def _ensure_capability_role(connection, role_name: str) -> None:
    """Require one stable capability role, with superuser-only fallback creation."""
    role_exists, current_user_is_superuser = connection.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role_name), "
            "COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER), FALSE)"
        ),
        {"role_name": role_name},
    ).one()
    if not role_exists and not current_user_is_superuser:
        raise CapabilityRoleBootstrapRequiredError(role_name)

    bootstrap_message = str(CapabilityRoleBootstrapRequiredError(role_name))
    connection.execute(
        text(
            "".join(
                (
                    "DO $fardb$ DECLARE capability_role text := :role_name; BEGIN "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = capability_role) THEN "
                    "IF NOT COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER), FALSE) THEN "
                    "RAISE EXCEPTION USING MESSAGE = :bootstrap_message; END IF; "
                    "EXECUTE 'CREATE ROLE ' || quote_ident(capability_role) || "
                    "' NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION'; "
                    "END IF; "
                    "IF EXISTS (SELECT 1 FROM pg_roles AS role WHERE role.rolname = capability_role "
                    "AND (role.rolcanlogin OR role.rolsuper OR role.rolcreatedb "
                    "OR role.rolcreaterole OR role.rolbypassrls OR role.rolreplication "
                    "OR has_database_privilege(role.oid, current_database(), 'CREATE') "
                    "OR has_schema_privilege(role.oid, current_schema(), 'CREATE') "
                    "OR EXISTS (SELECT 1 FROM pg_proc AS proc "
                    "JOIN pg_namespace AS namespace ON namespace.oid = proc.pronamespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND proc.proname = 'grac_v1_reject_mutation' AND proc.proowner = role.oid) OR EXISTS ("
                    "SELECT 1 FROM pg_auth_members AS membership WHERE membership.member = role.oid) OR EXISTS ("
                    "SELECT 1 FROM pg_auth_members AS membership "
                    "WHERE membership.roleid = role.oid AND membership.admin_option) OR (",
                    USABLE_ROLE_MEMBERSHIP_CTE_SQL,
                    "SELECT COUNT(*) FROM pg_roles AS grantee WHERE grantee.rolcanlogin "
                    "AND EXISTS (SELECT 1 FROM role_membership WHERE role_membership.member = grantee.oid "
                    "AND role_membership.roleid = role.oid)) > 1)) "
                    "THEN RAISE EXCEPTION USING MESSAGE = "
                    "'unsafe FarDB capability role: ' || capability_role; END IF; END $fardb$",
                )
            )
        ),
        {"role_name": role_name, "bootstrap_message": bootstrap_message},
    )


def _policy_creation_sql(
    table_name: str,
    policy_name: str,
    role_name: str,
    command: str,
    using_expression: str | None,
    check_expression: str | None,
) -> str:
    """Build DDL from repository-owned identifiers and boolean expressions."""
    parts = ["CREATE POLICY ", policy_name, " ON ", table_name, " FOR ", command, " TO ", role_name]
    if using_expression is not None:
        parts.extend((" USING (", using_expression, ")"))
    if check_expression is not None:
        parts.extend((" WITH CHECK (", check_expression, ")"))
    return "".join(parts)


def _unknown_runtime_policies(connection, managed_tables: list[str], policy_names: set[str]) -> list[str]:
    """Return non-contract policies attached to managed tables."""
    return (
        connection.execute(
            text(
                "SELECT policy.tablename || '.' || policy.policyname "
                "FROM pg_policies AS policy WHERE policy.schemaname = current_schema() "
                "AND policy.tablename IN :tables AND policy.policyname NOT IN :policy_names"
            ).bindparams(
                bindparam("tables", expanding=True),
                bindparam("policy_names", expanding=True),
            ),
            {"tables": managed_tables, "policy_names": sorted(policy_names)},
        )
        .scalars()
        .all()
    )


# Identifiers are derived only from ORM metadata and repository-owned role/policy constants.
# bearer:disable python_lang_sql_injection
def _reset_runtime_table_access(connection, managed_tables: list[str], policy_names: set[str]) -> None:
    """Reset managed-table grants and contract policy names before provisioning."""
    for table_name in managed_tables:
        connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table_name} FROM PUBLIC"))
        for role_name in RUNTIME_CAPABILITY_ROLES.values():
            connection.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table_name} FROM {role_name}"))
        for policy_name in policy_names:
            connection.execute(text(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}"))


def _reset_runtime_sequence_access(connection) -> None:
    """Reset graph-sequence grants before provisioning."""
    for table_name, column_name in _GRAPH_SEQUENCE_TABLE_COLUMNS:
        connection.execute(
            text(
                f"DO $fardb$ DECLARE sequence_name text := "
                f"pg_get_serial_sequence('{table_name}', '{column_name}'); BEGIN "
                f"IF sequence_name IS NOT NULL THEN EXECUTE format("
                f"'REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM PUBLIC', sequence_name); END IF; "
                f"END $fardb$"
            )
        )
        for role_name in RUNTIME_CAPABILITY_ROLES.values():
            connection.execute(
                text(
                    f"DO $fardb$ DECLARE sequence_name text := "
                    f"pg_get_serial_sequence('{table_name}', '{column_name}'); BEGIN "
                    f"IF sequence_name IS NOT NULL THEN EXECUTE format("
                    f"'REVOKE ALL PRIVILEGES ON SEQUENCE %s FROM {role_name}', sequence_name); END IF; "
                    f"END $fardb$"
                )
            )


def _grant_runtime_capability_access(connection, capabilities: tuple[str, ...], table_privileges: dict) -> None:
    """Grant the exact table, column, and sequence capability matrix."""
    for capability in capabilities:
        role_name = RUNTIME_CAPABILITY_ROLES[capability]
        connection.execute(
            text(
                f"DO $fardb$ BEGIN EXECUTE format("
                f"'GRANT USAGE ON SCHEMA %I TO {role_name}', current_schema()); END $fardb$"
            )
        )
        for (contract_capability, table_name), privileges in table_privileges.items():
            if contract_capability == capability:
                connection.execute(text(f"GRANT {', '.join(sorted(privileges))} ON TABLE {table_name} TO {role_name}"))
        if capability == GRAPH_RUNTIME_CAPABILITY:
            _grant_graph_runtime_access(connection, role_name)


# Identifiers are derived only from GRAC table/sequence constants and the runtime-role map.
# bearer:disable python_lang_sql_injection
def _grant_graph_runtime_access(connection, role_name: str) -> None:
    """Grant graph-only locking columns and sequence access."""
    from .relationship_assertion_db_models import GRAC_TABLE_NAMES

    for table_name in GRAC_TABLE_NAMES:
        connection.execute(text(f"GRANT UPDATE (id) ON TABLE {table_name} TO {role_name}"))
    for table_name, column_name in _GRAPH_SEQUENCE_TABLE_COLUMNS:
        connection.execute(
            text(
                f"DO $fardb$ DECLARE sequence_name text := "
                f"pg_get_serial_sequence('{table_name}', '{column_name}'); BEGIN "
                f"IF sequence_name IS NOT NULL THEN EXECUTE format("
                f"'GRANT USAGE, SELECT ON SEQUENCE %s TO {role_name}', sequence_name); END IF; "
                f"END $fardb$"
            )
        )


def _create_runtime_policies(connection, policy_specs: dict) -> None:
    """Create the exact named RLS policy matrix."""
    for (table_name, policy_name), (command_code, using_expression, check_expression) in policy_specs.items():
        capability = policy_name.split("_", 2)[1]
        connection.execute(
            text(
                _policy_creation_sql(
                    table_name,
                    policy_name,
                    RUNTIME_CAPABILITY_ROLES[capability],
                    _RLS_COMMAND_NAMES[command_code],
                    using_expression,
                    check_expression,
                )
            )
        )


# The explicit capability matrix is intentionally kept together for fail-closed auditability.
def ensure_runtime_database_capabilities(  # noqa: C901  # skipcq: PY-R1000
    engine: Engine,
    capabilities: tuple[str, ...] | set[str] | frozenset[str],
) -> None:
    """Install exact PostgreSQL grants and RLS policies for runtime capabilities."""
    normalized = _normalized_runtime_capabilities(capabilities)
    if make_url(engine.url).get_backend_name() != "postgresql" or not normalized:
        return

    table_privileges = _runtime_table_privileges(normalized)
    policy_specs = _runtime_policy_specs(normalized)
    all_policy_names = {
        f"fardb_{capability}_{command.lower()}_v1"
        for capability in RUNTIME_CAPABILITY_ROLES
        for command in _RLS_COMMANDS
    } | {"fardb_graph_lock_v1"}

    with engine.begin() as connection:
        managed_tables = sorted(Base.metadata.tables)
        unknown_policies = _unknown_runtime_policies(connection, managed_tables, all_policy_names)
        if unknown_policies:
            raise SchemaCompatibilityError(
                "managed tables contain unknown RLS policies: " + ", ".join(sorted(unknown_policies))
            )

        for role_name in RUNTIME_CAPABILITY_ROLES.values():
            _ensure_capability_role(connection, role_name)

        _reset_runtime_table_access(connection, managed_tables, all_policy_names)
        _reset_runtime_sequence_access(connection)
        _grant_runtime_capability_access(connection, normalized, table_privileges)
        _create_runtime_policies(connection, policy_specs)


def _verify_runtime_capability_roles(connection, capabilities: tuple[str, ...], managed_tables: list[str]) -> None:
    """Verify capability-role safety and schema access."""
    for capability in capabilities:
        role_name = RUNTIME_CAPABILITY_ROLES[capability]
        safe_role = connection.execute(
            text(
                "".join(
                    (
                        "SELECT COUNT(*) = 1 FROM pg_roles AS role WHERE role.rolname = :role_name "
                        "AND NOT role.rolcanlogin AND NOT role.rolsuper AND NOT role.rolcreatedb "
                        "AND NOT role.rolcreaterole AND NOT role.rolbypassrls AND NOT role.rolreplication "
                        "AND NOT has_database_privilege(role.oid, current_database(), 'CREATE') "
                        "AND NOT EXISTS (SELECT 1 FROM pg_class AS rel "
                        "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
                        "WHERE namespace.nspname = current_schema() "
                        "AND rel.relowner = role.oid "
                        "AND (rel.relname IN :tables OR (rel.relkind = 'S' "
                        "AND EXISTS (SELECT 1 FROM pg_depend AS dependency "
                        "JOIN pg_class AS owning_table ON owning_table.oid = dependency.refobjid "
                        "JOIN pg_namespace AS owning_namespace ON owning_namespace.oid = owning_table.relnamespace "
                        "WHERE dependency.classid = 'pg_class'::regclass "
                        "AND dependency.refclassid = 'pg_class'::regclass "
                        "AND dependency.objid = rel.oid "
                        "AND dependency.deptype IN ('a', 'i') "
                        "AND owning_namespace.nspname = current_schema() "
                        "AND owning_table.relname IN :sequence_tables)))) "
                        "AND NOT EXISTS (SELECT 1 FROM pg_proc AS proc "
                        "JOIN pg_namespace AS namespace ON namespace.oid = proc.pronamespace "
                        "WHERE namespace.nspname = current_schema() "
                        "AND proc.proname = 'grac_v1_reject_mutation' AND proc.proowner = role.oid) "
                        "AND NOT EXISTS (SELECT 1 FROM pg_auth_members AS membership "
                        "WHERE membership.member = role.oid) "
                        "AND NOT EXISTS (SELECT 1 FROM pg_auth_members AS membership "
                        "WHERE membership.roleid = role.oid AND membership.admin_option) AND (",
                        USABLE_ROLE_MEMBERSHIP_CTE_SQL,
                        "SELECT COUNT(*) FROM pg_roles AS grantee WHERE grantee.rolcanlogin "
                        "AND EXISTS (SELECT 1 FROM role_membership WHERE role_membership.member = grantee.oid "
                        "AND role_membership.roleid = role.oid)) <= 1",
                    )
                )
            ).bindparams(
                bindparam("tables", expanding=True),
                bindparam("sequence_tables", expanding=True),
            ),
            {"role_name": role_name, "tables": managed_tables, "sequence_tables": managed_tables},
        ).scalar_one()
        if not safe_role:
            raise SchemaCompatibilityError(f"unsafe or missing runtime capability role: {role_name}")
        schema_access = connection.execute(
            text(
                "SELECT has_schema_privilege(:role_name, current_schema(), 'USAGE') "
                "AND NOT has_schema_privilege(:role_name, current_schema(), 'CREATE')"
            ),
            {"role_name": role_name},
        ).scalar_one()
        if not schema_access:
            raise SchemaCompatibilityError(f"runtime schema grants do not match {capability} capability")


def _verify_runtime_rls_catalog(connection, managed_tables: list[str], policy_specs: dict) -> None:
    """Verify RLS enablement and the exact policy catalog."""
    rls_table_count = connection.execute(
        text(
            "SELECT COUNT(*) FROM pg_class AS rel "
            "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
            "WHERE namespace.nspname = current_schema() AND rel.relname IN :tables "
            "AND rel.relrowsecurity"
        ).bindparams(bindparam("tables", expanding=True)),
        {"tables": managed_tables},
    ).scalar_one()
    if rls_table_count != len(Base.metadata.tables):
        raise SchemaCompatibilityError("managed tables do not all have row-level security enabled")

    rows = connection.execute(
        text(
            "SELECT table_rel.relname, policy.polname, policy.polcmd, policy.polpermissive, "
            "CASE WHEN cardinality(policy.polroles) = 1 "
            "THEN pg_get_userbyid(policy.polroles[1]) ELSE '<invalid>' END, "
            "pg_get_expr(policy.polqual, policy.polrelid), "
            "pg_get_expr(policy.polwithcheck, policy.polrelid) "
            "FROM pg_policy AS policy "
            "JOIN pg_class AS table_rel ON table_rel.oid = policy.polrelid "
            "JOIN pg_namespace AS namespace ON namespace.oid = table_rel.relnamespace "
            "WHERE namespace.nspname = current_schema() AND table_rel.relname IN :tables"
        ).bindparams(bindparam("tables", expanding=True)),
        {"tables": managed_tables},
    ).all()
    actual_policies = {
        (table_name, policy_name): (command, permissive, role_name, using_expression, check_expression)
        for table_name, policy_name, command, permissive, role_name, using_expression, check_expression in rows
    }
    expected_policies = {
        (table_name, policy_name): (
            command,
            True,
            RUNTIME_CAPABILITY_ROLES[policy_name.split("_", 2)[1]],
            using_expression,
            check_expression,
        )
        for (table_name, policy_name), (command, using_expression, check_expression) in policy_specs.items()
    }
    if actual_policies != expected_policies:
        raise SchemaCompatibilityError("runtime RLS policy catalog does not match the capability contract")


def _table_privilege_rows(connection, role_names: Sequence[str | None], table_names: Sequence[str]) -> list[tuple]:
    """Return the complete requested table-privilege matrix in one round trip."""
    return connection.execute(
        text(
            "WITH requested_roles(role_name) AS (SELECT unnest(CAST(:role_names AS text[]))), "
            "requested_tables(table_name) AS (SELECT unnest(CAST(:table_names AS text[]))), "
            "requested_privileges(privilege) AS (SELECT unnest(CAST(:privileges AS text[]))) "
            "SELECT role_name, table_name, privilege, "
            "has_table_privilege(COALESCE(role_name, session_user), table_name, privilege) "
            "FROM requested_roles CROSS JOIN requested_tables CROSS JOIN requested_privileges"
        ),
        {"role_names": role_names, "table_names": table_names, "privileges": list(_TABLE_PRIVILEGES)},
    ).all()


def _column_privilege_rows(connection, role_names: Sequence[str | None], table_names: Sequence[str]) -> list[tuple]:
    """Return the complete requested column-privilege matrix in one round trip."""
    column_tables: list[str] = []
    column_names: list[str] = []
    for table_name in table_names:
        for column_name in Base.metadata.tables[table_name].columns.keys():
            column_tables.append(table_name)
            column_names.append(column_name)
    return connection.execute(
        text(
            "WITH requested_roles(role_name) AS (SELECT unnest(CAST(:role_names AS text[]))), "
            "requested_columns(table_name, column_name) AS ("
            "SELECT * FROM unnest(CAST(:column_tables AS text[]), CAST(:column_names AS text[]))), "
            "requested_privileges(privilege) AS (SELECT unnest(CAST(:privileges AS text[]))) "
            "SELECT role_name, table_name, column_name, privilege, "
            "has_column_privilege(COALESCE(role_name, session_user), table_name, column_name, privilege) "
            "FROM requested_roles CROSS JOIN requested_columns CROSS JOIN requested_privileges"
        ),
        {
            "role_names": role_names,
            "column_tables": column_tables,
            "column_names": column_names,
            "privileges": list(_COLUMN_PRIVILEGES),
        },
    ).all()


def _sequence_privilege_rows(connection, role_names: Sequence[str | None]) -> list[tuple]:
    """Return the complete requested application-sequence matrix in one round trip."""
    table_names, column_names = zip(*_GRAPH_SEQUENCE_TABLE_COLUMNS, strict=True)
    return connection.execute(
        text(
            "WITH requested_roles(role_name) AS (SELECT unnest(CAST(:role_names AS text[]))), "
            "requested_sequences(table_name, column_name) AS ("
            "SELECT * FROM unnest(CAST(:table_names AS text[]), CAST(:column_names AS text[]))), "
            "requested_privileges(privilege) AS (SELECT unnest(CAST(:privileges AS text[]))) "
            "SELECT role_name, table_name, column_name, sequence_name, privilege, "
            "has_sequence_privilege(COALESCE(role_name, session_user), sequence_name, privilege) "
            "FROM requested_roles CROSS JOIN requested_sequences "
            "CROSS JOIN LATERAL (SELECT pg_get_serial_sequence(table_name, column_name) AS sequence_name) resolved "
            "CROSS JOIN requested_privileges"
        ),
        {
            "role_names": role_names,
            "table_names": list(table_names),
            "column_names": list(column_names),
            "privileges": list(_SEQUENCE_PRIVILEGES),
        },
    ).all()


def _first_matrix_mismatch(actual_rows: list[tuple], expected: dict[tuple, bool]) -> tuple | None:
    """Return the first missing, extra, or incompatible privilege-matrix key."""
    actual = {tuple(row[:-1]): bool(row[-1]) if row[-1] is not None else None for row in actual_rows}
    if actual.keys() != expected.keys():
        return next(iter(actual.keys() ^ expected.keys()))
    return next((key for key, expected_value in expected.items() if actual[key] != expected_value), None)


def _expected_capability_table_grants(
    capability: str,
    role_name: str,
    managed_tables: list[str],
    table_privileges: dict,
) -> dict[tuple, bool]:
    """Build one capability's expected table-privilege matrix."""
    return {
        (role_name, table_name, privilege): privilege in table_privileges.get((capability, table_name), frozenset())
        for table_name in managed_tables
        for privilege in _TABLE_PRIVILEGES
    }


def _expected_capability_column_grants(
    capability: str,
    role_name: str,
    managed_tables: list[str],
    table_privileges: dict,
    grac_tables: frozenset[str],
) -> dict[tuple, bool]:
    """Build one capability's expected column-privilege matrix."""
    return {
        (role_name, table_name, column_name, privilege): (
            privilege in table_privileges.get((capability, table_name), frozenset())
            or (
                privilege == "UPDATE"
                and capability == GRAPH_RUNTIME_CAPABILITY
                and table_name in grac_tables
                and column_name == "id"
            )
        )
        for table_name in managed_tables
        for column_name in Base.metadata.tables[table_name].columns.keys()
        for privilege in _COLUMN_PRIVILEGES
    }


def _expected_capability_sequence_grants(capability: str, role_name: str) -> dict[tuple, bool]:
    """Build one capability's expected sequence-privilege matrix."""
    return {
        (role_name, table_name, column_name, privilege): (
            capability == GRAPH_RUNTIME_CAPABILITY and privilege in _GRAPH_SEQUENCE_PRIVILEGES
        )
        for table_name, column_name in _GRAPH_SEQUENCE_TABLE_COLUMNS
        for privilege in _SEQUENCE_PRIVILEGES
    }


def _verify_runtime_capability_grants(
    connection,
    capabilities: tuple[str, ...],
    managed_tables: list[str],
    table_privileges: dict,
    grac_tables: frozenset[str],
) -> None:
    """Verify the complete table, column, and sequence grant matrices."""
    role_names = [RUNTIME_CAPABILITY_ROLES[capability] for capability in capabilities]
    capability_by_role = {RUNTIME_CAPABILITY_ROLES[capability]: capability for capability in capabilities}
    expected_tables: dict[tuple, bool] = {}
    expected_columns: dict[tuple, bool] = {}
    expected_sequences: dict[tuple, bool] = {}
    for capability in capabilities:
        role_name = RUNTIME_CAPABILITY_ROLES[capability]
        expected_tables.update(
            _expected_capability_table_grants(capability, role_name, managed_tables, table_privileges)
        )
        expected_columns.update(
            _expected_capability_column_grants(
                capability,
                role_name,
                managed_tables,
                table_privileges,
                grac_tables,
            )
        )
        expected_sequences.update(_expected_capability_sequence_grants(capability, role_name))

    mismatch = _first_matrix_mismatch(_table_privilege_rows(connection, role_names, managed_tables), expected_tables)
    if mismatch is not None:
        role_name, table_name, _privilege = mismatch
        raise SchemaCompatibilityError(
            f"runtime grants do not match {capability_by_role[role_name]} capability on {table_name}"
        )
    mismatch = _first_matrix_mismatch(_column_privilege_rows(connection, role_names, managed_tables), expected_columns)
    if mismatch is not None:
        role_name, table_name, _column_name, _privilege = mismatch
        raise SchemaCompatibilityError(
            f"runtime column grants do not match {capability_by_role[role_name]} capability on {table_name}"
        )
    sequence_rows = _sequence_privilege_rows(connection, role_names)
    missing_sequence = next((row[1] for row in sequence_rows if row[3] is None), None)
    if missing_sequence is not None:
        raise SchemaCompatibilityError(f"required runtime sequence is missing for {missing_sequence}")
    comparable_sequence_rows = [(row[0], row[1], row[2], row[4], row[5]) for row in sequence_rows]
    mismatch = _first_matrix_mismatch(comparable_sequence_rows, expected_sequences)
    if mismatch is not None:
        role_name, table_name, _column_name, _privilege = mismatch
        raise SchemaCompatibilityError(
            f"runtime sequence grants do not match {capability_by_role[role_name]} capability on {table_name}"
        )


# The catalog verifier intentionally exposes each privilege edge in one auditable matrix.
def _verify_runtime_capability_catalog(connection, capabilities: tuple[str, ...]) -> None:
    """Verify exact role attributes, table grants, and named RLS policies."""
    from .relationship_assertion_db_models import GRAC_TABLE_NAMES

    managed_tables = sorted(Base.metadata.tables)
    table_privileges = _runtime_table_privileges(capabilities)
    policy_specs = _runtime_policy_specs(capabilities)
    _verify_runtime_capability_roles(connection, capabilities, managed_tables)
    _verify_runtime_rls_catalog(connection, managed_tables, policy_specs)
    _verify_runtime_capability_grants(
        connection,
        capabilities,
        managed_tables,
        table_privileges,
        frozenset(GRAC_TABLE_NAMES),
    )


def _verify_runtime_login_relation_grants(connection, capabilities: tuple[str, ...]) -> None:
    """Verify effective login relation privileges in two set-based round trips."""
    from .relationship_assertion_db_models import GRAC_TABLE_NAMES

    effective_privileges = _runtime_table_privileges(capabilities)
    grac_tables = frozenset(GRAC_TABLE_NAMES)
    graph_lock_columns = (
        frozenset((table_name, "id") for table_name in grac_tables)
        if GRAPH_RUNTIME_CAPABILITY in capabilities
        else frozenset()
    )
    managed_tables = sorted(Base.metadata.tables)
    expected_tables: dict[tuple, bool] = {}
    expected_columns: dict[tuple, bool] = {}
    for table_name in managed_tables:
        expected = frozenset(
            privilege
            for capability in capabilities
            for privilege in effective_privileges.get((capability, table_name), frozenset())
        )
        for privilege in _TABLE_PRIVILEGES:
            expected_tables[(None, table_name, privilege)] = privilege in expected
        for column_name in Base.metadata.tables[table_name].columns.keys():
            for privilege in _COLUMN_PRIVILEGES:
                expected_columns[(None, table_name, column_name, privilege)] = privilege in expected or (
                    privilege == "UPDATE" and (table_name, column_name) in graph_lock_columns
                )

    mismatch = _first_matrix_mismatch(_table_privilege_rows(connection, [None], managed_tables), expected_tables)
    if mismatch is not None:
        _role_name, table_name, _privilege = mismatch
        raise SchemaCompatibilityError(f"runtime login grants are incompatible on {table_name}")
    mismatch = _first_matrix_mismatch(_column_privilege_rows(connection, [None], managed_tables), expected_columns)
    if mismatch is not None:
        _role_name, table_name, _column_name, _privilege = mismatch
        raise SchemaCompatibilityError(f"runtime login column grants are incompatible on {table_name}")


def _verify_runtime_login_sequence_grants(
    connection,
    capabilities: tuple[str, ...],
) -> None:
    """Verify effective login sequence privileges in one set-based round trip."""
    expected_privileges = _GRAPH_SEQUENCE_PRIVILEGES if GRAPH_RUNTIME_CAPABILITY in capabilities else frozenset()
    expected_sequences: dict[tuple, bool] = {}
    for table_name, column_name in _GRAPH_SEQUENCE_TABLE_COLUMNS:
        for privilege in _SEQUENCE_PRIVILEGES:
            expected_sequences[(None, table_name, column_name, privilege)] = privilege in expected_privileges

    sequence_rows = _sequence_privilege_rows(connection, [None])
    missing_sequence = next((row[1] for row in sequence_rows if row[3] is None), None)
    if missing_sequence is not None:
        raise SchemaCompatibilityError(f"required runtime sequence is missing for {missing_sequence}")
    comparable_sequence_rows = [(row[0], row[1], row[2], row[4], row[5]) for row in sequence_rows]
    mismatch = _first_matrix_mismatch(comparable_sequence_rows, expected_sequences)
    if mismatch is not None:
        _role_name, table_name, _column_name, _privilege = mismatch
        raise SchemaCompatibilityError(f"runtime login sequence grants are incompatible on {table_name}")


def verify_database_schema(
    engine: Engine,
    *,
    required_capabilities: tuple[str, ...] | set[str] | frozenset[str] = (),
) -> None:
    """Verify the asset-store schema without creating, altering, or repairing it.

    The explicit operator migration path remains responsible for every schema
    mutation. Runtime callers use this function to fail closed when required
    tables, columns, constraints, indexes, or GRAC authority guards are absent.

    Parameters:
        engine: SQLAlchemy engine connected with runtime application authority.

    Raises:
        SchemaCompatibilityError: If the schema or authority posture is not compatible.
    """
    # Register every ORM table on Base.metadata before comparing the live schema.
    from . import relationship_assertion_db_models as _relationship_assertion_db_models  # noqa: F401
    from .migrations import postgresql_heartbeat_schema_gaps
    from .relationship_assertion_schema import verify_relationship_assertion_schema

    backend = make_url(engine.url).get_backend_name()
    if backend == "sqlite":
        # Connection-local UDF/pragma setup is not persistent schema mutation.
        configure_sqlite_engine(engine)

    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names())
        expected_tables = set(Base.metadata.tables)
        missing_tables = sorted(expected_tables - actual_tables)
        if missing_tables:
            raise SchemaCompatibilityError(f"database schema missing required tables: {', '.join(missing_tables)}")

        for table_name in sorted(expected_tables):
            _verify_table_schema(inspector, table_name)

        if backend == "postgresql":
            heartbeat_gaps = postgresql_heartbeat_schema_gaps(inspector)
            if heartbeat_gaps:
                raise SchemaCompatibilityError(
                    "database rebuild compatibility requirements are missing: " + ", ".join(heartbeat_gaps)
                )

        verify_relationship_assertion_schema(engine)
        normalized_capabilities = _normalized_runtime_capabilities(required_capabilities)
        if backend == "postgresql" and normalized_capabilities:
            with engine.connect() as connection:
                _verify_runtime_capability_catalog(connection, normalized_capabilities)
    except SchemaCompatibilityError:
        raise
    except (PermissionError, RuntimeError) as exc:
        # GRAC verification emits bounded repository-owned invariant messages.
        raise SchemaCompatibilityError(str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - sanitize driver/catalog errors at the runtime boundary
        raise SchemaCompatibilityError(
            f"database schema compatibility verification failed ({type(exc).__name__})"
        ) from None


def verify_runtime_database_authority(  # skipcq: PY-R1000
    engine: Engine,
    *,
    required_capabilities: tuple[str, ...] | set[str] | frozenset[str] = (),
) -> None:
    """Require a PostgreSQL runtime role without schema-migration authority."""
    backend = make_url(engine.url).get_backend_name()
    if backend != "postgresql":
        return

    normalized_capabilities = _normalized_runtime_capabilities(required_capabilities)
    try:
        managed_tables = sorted(Base.metadata.tables)
        with engine.connect() as connection:
            restricted = connection.execute(
                text(
                    "SELECT current_schema() IS NOT NULL AND NOT EXISTS ("
                    "SELECT 1 FROM pg_roles AS assumable "
                    "WHERE (assumable.oid = login.oid "
                    "OR CASE WHEN current_setting('server_version_num')::integer >= 160000 THEN "
                    "(pg_has_role(login.oid, assumable.oid, 'USAGE') "
                    "OR pg_has_role(login.oid, assumable.oid, 'SET')) "
                    "ELSE pg_has_role(login.oid, assumable.oid, 'MEMBER') END) "
                    "AND (assumable.rolsuper OR assumable.rolcreaterole "
                    "OR assumable.rolcreatedb OR assumable.rolbypassrls OR assumable.rolreplication "
                    "OR has_database_privilege(assumable.oid, current_database(), 'CREATE') "
                    "OR has_schema_privilege(assumable.oid, current_schema(), 'CREATE') "
                    "OR EXISTS (SELECT 1 FROM pg_namespace AS namespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND namespace.nspowner = assumable.oid) "
                    "OR EXISTS (SELECT 1 FROM pg_database AS database "
                    "WHERE database.datname = current_database() "
                    "AND database.datdba = assumable.oid) "
                    "OR EXISTS (SELECT 1 FROM pg_class AS rel "
                    "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND rel.relowner = assumable.oid "
                    "AND (rel.relname IN :tables OR (rel.relkind = 'S' "
                    "AND EXISTS (SELECT 1 FROM pg_depend AS dependency "
                    "JOIN pg_class AS owning_table ON owning_table.oid = dependency.refobjid "
                    "JOIN pg_namespace AS owning_namespace ON owning_namespace.oid = owning_table.relnamespace "
                    "WHERE dependency.classid = 'pg_class'::regclass "
                    "AND dependency.refclassid = 'pg_class'::regclass "
                    "AND dependency.objid = rel.oid "
                    "AND dependency.deptype IN ('a', 'i') "
                    "AND owning_namespace.nspname = current_schema() "
                    "AND owning_table.relname IN :sequence_tables)))) "
                    "OR EXISTS (SELECT 1 FROM pg_proc AS proc "
                    "JOIN pg_namespace AS namespace ON namespace.oid = proc.pronamespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND proc.proname = 'grac_v1_reject_mutation' "
                    "AND proc.proowner = assumable.oid))) "
                    "FROM pg_roles AS login WHERE login.rolname = session_user"
                ).bindparams(
                    bindparam("tables", expanding=True),
                    bindparam("sequence_tables", expanding=True),
                ),
                {"tables": managed_tables, "sequence_tables": managed_tables},
            ).scalar_one()
            if not restricted:
                raise SchemaCompatibilityError("runtime database role retains schema-migration authority")
            expected_roles = {RUNTIME_CAPABILITY_ROLES[name] for name in normalized_capabilities}
            actual_roles = set(
                connection.execute(
                    text(
                        "SELECT assumable.rolname FROM pg_roles AS login "
                        "JOIN pg_roles AS assumable ON assumable.oid <> login.oid "
                        "AND CASE WHEN current_setting('server_version_num')::integer >= 160000 THEN "
                        "(pg_has_role(login.oid, assumable.oid, 'USAGE') "
                        "OR pg_has_role(login.oid, assumable.oid, 'SET')) "
                        "ELSE pg_has_role(login.oid, assumable.oid, 'MEMBER') END "
                        "WHERE login.rolname = session_user"
                    )
                )
                .scalars()
                .all()
            )
            if actual_roles != expected_roles:
                raise SchemaCompatibilityError("runtime login capability memberships are incompatible")
            if normalized_capabilities:
                _verify_runtime_capability_catalog(connection, normalized_capabilities)
            _verify_runtime_login_relation_grants(connection, normalized_capabilities)
            _verify_runtime_login_sequence_grants(connection, normalized_capabilities)
    except SchemaCompatibilityError:
        raise
    except Exception as exc:  # noqa: BLE001 - sanitize driver/catalog errors at the runtime boundary
        raise SchemaCompatibilityError(
            f"runtime database authority verification failed ({type(exc).__name__})"
        ) from None
