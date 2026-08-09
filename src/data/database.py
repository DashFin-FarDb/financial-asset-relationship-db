"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy import (  # pyre-ignore[21]
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
    bindparam,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Engine, make_url  # pyre-ignore[21]
from sqlalchemy.exc import ArgumentError  # pyre-ignore[21]
from sqlalchemy.orm import Session, sessionmaker  # pyre-ignore[21]
from sqlalchemy.pool import StaticPool  # pyre-ignore[21]

from src.config.settings import get_settings

from .base import Base

# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"
ASSET_GRAPH_DATABASE_URL_ENV_VAR = "ASSET_GRAPH_DATABASE_URL"
SQLITE_MEMORY_DATABASE = ":memory:"
_SQL_IDENTIFIER_PATTERN = re.compile(r"[a-z_][a-z0-9_$]*")
_POSTGRESQL_ANY_ARRAY_PATTERN = re.compile(r"=\s*any\s*\(\s*\(?\s*array\s*\[([^\]]*)\]\s*\)?\s*\)")
# Identifier/number, or a simple function call such as length(strength).
_CHECK_TOKEN_PATTERN = r"(?:[a-z_][a-z0-9_.$]*(?:\([^()]*\))?|\d+(?:\.\d+)?)"
_BETWEEN_PREDICATE_PATTERN = re.compile(
    rf"\b({_CHECK_TOKEN_PATTERN})\s+between\s+({_CHECK_TOKEN_PATTERN})\s+and\s+({_CHECK_TOKEN_PATTERN})"
)
_IN_LITERAL_SET_PATTERN = re.compile(r"\bin\s*\(([^()]*)\)")


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


def _consume_quoted_sql_token(definition: str, start: int, quote: str) -> tuple[str, int]:
    """Return one quoted SQL token and the next scan position."""
    position = start + 1
    while position < len(definition):
        if definition[position] != quote:
            position += 1
            continue
        if position + 1 < len(definition) and definition[position + 1] == quote:
            position += 2
            continue
        return definition[start : position + 1], position + 1
    return definition[start:position], position


def _canonicalize_quoted_sql_token(token: str, quote: str) -> str:
    """Unquote simple PostgreSQL identifiers while preserving string literals."""
    if quote != '"' or not token.endswith('"'):
        return token
    identifier = token[1:-1]
    if _SQL_IDENTIFIER_PATTERN.fullmatch(identifier):
        return identifier
    return token


def _protect_quoted_sql_tokens(definition: str) -> tuple[str, dict[str, str]]:
    """Replace quoted SQL tokens with markers before syntax canonicalisation."""
    protected: dict[str, str] = {}
    output: list[str] = []
    position = 0

    while position < len(definition):
        quote = definition[position]
        if quote not in {"'", '"'}:
            output.append(quote)
            position += 1
            continue

        token, position = _consume_quoted_sql_token(definition, position, quote)
        marker = f"\x00fardb_quoted_{len(protected)}\x00"
        protected[marker] = _canonicalize_quoted_sql_token(token, quote)
        output.append(marker)

    return "".join(output), protected


def _restore_quoted_sql_tokens(definition: str, protected: dict[str, str]) -> str:
    """Restore quoted SQL tokens after syntax canonicalisation."""
    for marker, token in protected.items():
        definition = definition.replace(marker, token)
    return definition


def _normalize_check_definition(definition: object) -> str:
    """Normalize ORM and reflected CHECK SQL without weakening its predicate."""
    raw_definition = "" if definition is None else str(definition)
    normalized, protected = _protect_quoted_sql_tokens(raw_definition)
    normalized = normalized.lower().strip()
    normalized = re.sub(r"::\s*(?:character varying|text)(?:\[\])?", "", normalized)
    normalized = normalized.removeprefix("check")
    normalized = normalized.replace("!~~", "not like").replace("~~", "like")
    normalized = _POSTGRESQL_ANY_ARRAY_PATTERN.sub(r" in (\1)", normalized)
    normalized = _BETWEEN_PREDICATE_PATTERN.sub(r"\1 >= \2 and \1 <= \3", normalized)

    def _sort_literal_set(match: re.Match[str]) -> str:
        literals = [item.strip() for item in match.group(1).split(",")]
        if literals and all(item in protected and protected[item].startswith("'") for item in literals):
            return "in(" + ",".join(sorted(literals, key=protected.__getitem__)) + ")"
        return match.group(0)

    normalized = _IN_LITERAL_SET_PATTERN.sub(_sort_literal_set, normalized)
    normalized = re.sub(r'[\s()"]+', "", normalized)
    return _restore_quoted_sql_tokens(normalized, protected)


def _verify_required_columns(expected_table, actual_columns: set[str], table_name: str) -> None:
    """Verify that all ORM columns exist in the reflected table."""
    missing_columns = sorted(set(expected_table.columns.keys()) - actual_columns)
    if missing_columns:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required columns: {', '.join(missing_columns)}"
        )


def _expected_check_definitions(expected_table) -> dict[str, str]:
    """Return normalized named CHECK definitions from ORM metadata."""
    return {
        str(constraint.name): _normalize_check_definition(constraint.sqltext)
        for constraint in expected_table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }


def _reflected_check_definitions(inspector, table_name: str) -> dict[str, str]:
    """Return normalized named CHECK definitions from a live table."""
    return {
        str(constraint["name"]): _normalize_check_definition(constraint.get("sqltext"))
        for constraint in inspector.get_check_constraints(table_name)
        if constraint.get("name")
    }


def _verify_named_definitions(
    table_name: str,
    expected: Mapping[str, object],
    actual: Mapping[str, object],
    invariant: str,
) -> None:
    """Compare named schema definitions and raise bounded compatibility errors."""
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise SchemaCompatibilityError(
            f"database table {table_name} missing required {invariant}: {', '.join(missing)}"
        )
    mismatched = sorted(name for name, definition in expected.items() if actual[name] != definition)
    if mismatched:
        raise SchemaCompatibilityError(
            f"database table {table_name} has incompatible {invariant}: {', '.join(mismatched)}"
        )


def _expected_index_definitions(expected_table) -> dict[str, tuple[tuple[str, ...], bool]]:
    """Return expected index columns and uniqueness by index name."""
    return {
        str(index.name): (tuple(column.name for column in index.columns), bool(index.unique))
        for index in expected_table.indexes
        if index.name
    }


def _reflected_index_definitions(inspector, table_name: str) -> dict[str, tuple[tuple[str, ...], bool]]:
    """Return reflected index columns and uniqueness by index name."""
    return {
        str(index["name"]): (tuple(index.get("column_names") or ()), bool(index.get("unique")))
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def _verify_table_schema(inspector, table_name: str) -> None:
    """Verify columns and named schema invariants for one ORM table."""
    expected_table = Base.metadata.tables[table_name]
    actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
    _verify_required_columns(expected_table, actual_columns, table_name)
    _verify_named_definitions(
        table_name,
        _expected_check_definitions(expected_table),
        _reflected_check_definitions(inspector, table_name),
        "constraints",
    )
    _verify_named_definitions(
        table_name,
        _expected_index_definitions(expected_table),
        _reflected_index_definitions(inspector, table_name),
        "indexes",
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
