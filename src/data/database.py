"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import re

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

# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"
ASSET_GRAPH_DATABASE_URL_ENV_VAR = "ASSET_GRAPH_DATABASE_URL"
SQLITE_MEMORY_DATABASE = ":memory:"


class SchemaCompatibilityError(RuntimeError):
    """Raised when a runtime database does not match the required schema contract."""


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


def _normalize_check_definition(definition: object) -> str:
    """Normalize ORM and reflected CHECK SQL without weakening its predicate."""
    normalized = "" if definition is None else str(definition).lower()
    normalized = re.sub(r"::\s*(?:character varying|text)(?:\[\])?", "", normalized)
    normalized = normalized.removeprefix("check")
    normalized = normalized.replace("!~~", "not like").replace("~~", "like")
    normalized = re.sub(
        r"=\s*any\s*\(\s*\(?\s*array\s*\[([^\]]*)\]\s*\)?\s*\)",
        r" in (\1)",
        normalized,
    )
    normalized = re.sub(
        r"([^\s()]+)\s+between\s+([^\s()]+)\s+and\s+([^\s()]+)",
        r"\1 >= \2 and \1 <= \3",
        normalized,
    )

    def _sort_literal_set(match: re.Match[str]) -> str:
        literals = re.findall(r"'[^']*'", match.group(1))
        remainder = re.sub(r"'[^']*'|[\s,]", "", match.group(1))
        return "in(" + ",".join(sorted(literals)) + ")" if literals and not remainder else match.group(0)

    normalized = re.sub(r"\bin\s*\(([^()]*)\)", _sort_literal_set, normalized)
    return re.sub(r'[\s()"]+', "", normalized)


def _verify_table_schema(inspector, table_name: str) -> None:
    """Verify columns and named schema invariants for one ORM table."""
    expected_table = Base.metadata.tables[table_name]
    actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
    missing_columns = sorted(set(expected_table.columns.keys()) - actual_columns)
    if missing_columns:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required columns: {', '.join(missing_columns)}"
        )

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

    expected_indexes = {
        str(index.name): (tuple(column.name for column in index.columns), bool(index.unique))
        for index in expected_table.indexes
        if index.name
    }
    actual_indexes = {
        str(index["name"]): (tuple(index.get("column_names") or ()), bool(index.get("unique")))
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }
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

    _verify_table_constraints(inspector, table_name, expected_table)


def verify_database_schema(engine: Engine) -> None:
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
    except SchemaCompatibilityError:
        raise
    except (PermissionError, RuntimeError) as exc:
        # GRAC verification emits bounded repository-owned invariant messages.
        raise SchemaCompatibilityError(str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - sanitize driver/catalog errors at the runtime boundary
        raise SchemaCompatibilityError(
            f"database schema compatibility verification failed ({type(exc).__name__})"
        ) from None


def verify_runtime_database_authority(engine: Engine) -> None:
    """Require a PostgreSQL runtime role without schema-migration authority."""
    backend = make_url(engine.url).get_backend_name()
    if backend != "postgresql":
        return

    try:
        with engine.connect() as connection:
            restricted = connection.execute(
                text(
                    "SELECT current_schema() IS NOT NULL AND NOT EXISTS ("
                    "SELECT 1 FROM pg_roles AS assumable "
                    "WHERE (assumable.oid = login.oid "
                    "OR pg_has_role(login.oid, assumable.oid, 'MEMBER')) "
                    "AND (assumable.rolsuper OR assumable.rolcreaterole "
                    "OR assumable.rolcreatedb OR assumable.rolbypassrls "
                    "OR has_schema_privilege(assumable.oid, current_schema(), 'CREATE') "
                    "OR EXISTS (SELECT 1 FROM pg_namespace AS namespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND namespace.nspowner = assumable.oid) "
                    "OR EXISTS (SELECT 1 FROM pg_database AS database "
                    "WHERE database.datname = current_database() "
                    "AND database.datdba = assumable.oid) "
                    "OR EXISTS (SELECT 1 FROM pg_class AS rel "
                    "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
                    "WHERE namespace.nspname = current_schema() AND rel.relname IN :tables "
                    "AND rel.relowner = assumable.oid) "
                    "OR EXISTS (SELECT 1 FROM pg_proc AS proc "
                    "JOIN pg_namespace AS namespace ON namespace.oid = proc.pronamespace "
                    "WHERE namespace.nspname = current_schema() "
                    "AND proc.proname = 'grac_v1_reject_mutation' "
                    "AND proc.proowner = assumable.oid))) "
                    "FROM pg_roles AS login WHERE login.rolname = session_user"
                ).bindparams(bindparam("tables", expanding=True)),
                {"tables": sorted(Base.metadata.tables)},
            ).scalar_one()
        if not restricted:
            raise SchemaCompatibilityError("runtime database role retains schema-migration authority")
    except SchemaCompatibilityError:
        raise
    except Exception as exc:  # noqa: BLE001 - sanitize driver/catalog errors at the runtime boundary
        raise SchemaCompatibilityError(
            f"runtime database authority verification failed ({type(exc).__name__})"
        ) from None
