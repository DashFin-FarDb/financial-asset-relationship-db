"""
SQL migration helpers for rebuild schema compatibility.

This module provides a lightweight migration runner for SQLite databases
and a targeted compatibility migration for PostgreSQL heartbeat columns.
For broader cross-backend schema management, use Alembic or a similar tool.

Security:
    All SQL migrations are read from trusted version-controlled files in the
    migrations/ directory and validated against an ALLOWED_MIGRATIONS whitelist.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector

from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

logger = logging.getLogger(__name__)

# Explicit whitelist of allowed migration files
# Only migrations listed here can be executed (defense in depth)
ALLOWED_MIGRATIONS = frozenset(
    [
        "001_initial.sql",
        "002_add_heartbeat_columns.sql",
        "003_add_execution_identity_and_checkpoint_columns.sql",
        "004_add_cancellation_columns.sql",
    ]
)

_REBUILD_JOBS_TABLE_INFO_QUERY = "PRAGMA table_info(rebuild_jobs)"
REBUILD_JOB_STATUSES = (
    "pending",
    "running",
    "succeeded",
    "failed",
    "cancel_requested",
    "cancelled",
)
_REBUILD_JOB_STATUS_LITERALS = ", ".join(f"'{status}'" for status in REBUILD_JOB_STATUSES)
_REBUILD_IDENTIFIER_COLUMNS = ("active_worker_id", "execution_id")


def apply_migrations(db_path: Path | str) -> None:
    """
    Apply all pending SQL migrations to a SQLite database.

    This function is SQLite-specific and will not work with PostgreSQL or other databases.
    For non-SQLite databases, use Alembic or implement backend-specific migrations.

    This function applies migrations in order:
    1. 001_initial.sql - Base schema (idempotent via IF NOT EXISTS)
    2. 002_add_heartbeat_columns.sql - Upgrade migration (applied conditionally)
    3. 003_add_execution_identity_and_checkpoint_columns.sql - Upgrade migration (applied conditionally)
    4. 004_add_cancellation_columns.sql - Upgrade migration (applied conditionally)

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        ValueError: If db_path is not a valid SQLite database path.
    """
    db_path = Path(db_path)
    # migrations/ is at repository root, not under src/
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    from contextlib import closing

    with closing(sqlite3.connect(db_path)) as connection, connection:
        # Migration 001: Base schema (always safe to run, uses IF NOT EXISTS)
        _apply_sql_migration(connection, migrations_dir / "001_initial.sql")

        # Migration 002: Add heartbeat columns (conditional, check first)
        _apply_upgrade_002_heartbeat_columns(connection)

        # Migration 003: Add execution identity and checkpoint columns (conditional)
        _apply_upgrade_003_execution_columns(connection)

        # Migration 004: Add cancellation columns (conditional)
        _apply_upgrade_004_cancellation_columns(connection)


# ---------------------------------------------------------------------------
# Private helpers for apply_migrations (SQLite)
# ---------------------------------------------------------------------------


def _apply_sql_migration(connection: sqlite3.Connection, migration_file: Path) -> None:
    """
    Apply a SQL migration script from a trusted file path.

    Args:
        connection: SQLite connection.
        migration_file: Path to the SQL file. Must be within the migrations directory
            and listed in the ALLOWED_MIGRATIONS whitelist.

    Raises:
        ValueError: If migration file path is invalid, outside migrations directory,
            or not in the allowed migrations whitelist.
    """
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    try:
        resolved_file = migration_file.resolve()
        resolved_file.relative_to(migrations_dir)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Migration file {migration_file} is not within trusted migrations directory") from exc

    if not resolved_file.is_file():
        raise ValueError(f"Migration file {migration_file} does not exist")

    if resolved_file.suffix.lower() != ".sql":
        raise ValueError(f"Migration file {migration_file} must have .sql extension")

    if resolved_file.name not in ALLOWED_MIGRATIONS:
        raise ValueError(
            f"Migration file {resolved_file.name} is not in the allowed migrations whitelist. "
            f"Allowed: {sorted(ALLOWED_MIGRATIONS)}"
        )

    trusted_migration_sql = resolved_file.read_text(encoding="utf-8")  # noqa: S3649
    # Execute validated migration from trusted source
    # SECURITY: This is NOT user-controlled data. The SQL content comes from:
    # - A file that passed all validation checks above
    # - A filename that is hardcoded in ALLOWED_MIGRATIONS constant
    # - A directory that is source-controlled (migrations/)
    # - Version control system (git), not runtime user input
    # Suppressing false positive security warnings (B608, S608, S3649)
    connection.executescript(trusted_migration_sql)  # nosec B608  # noqa: S3649


def _apply_upgrade_002_heartbeat_columns(connection: sqlite3.Connection) -> None:
    """
    Apply migration 002 (add heartbeat columns) conditionally.

    Checks if columns exist before running ALTER TABLE statements,
    since SQLite's ALTER TABLE ADD COLUMN is not idempotent.

    Args:
        connection: SQLite connection.
    """
    cursor = connection.execute(_REBUILD_JOBS_TABLE_INFO_QUERY)
    existing_columns = {row[1] for row in cursor}

    HEARTBEAT_COLUMNS = {
        "active_worker_id": "ALTER TABLE rebuild_jobs ADD COLUMN active_worker_id TEXT",
        "last_heartbeat_at": "ALTER TABLE rebuild_jobs ADD COLUMN last_heartbeat_at TEXT",
    }

    for col_name, alter_statement in HEARTBEAT_COLUMNS.items():
        if col_name not in existing_columns:
            connection.execute(alter_statement)  # noqa: S3649


def _apply_upgrade_003_execution_columns(connection: sqlite3.Connection) -> None:
    """
    Apply migration 003 (add execution identity and checkpoint columns) conditionally.

    Args:
        connection: SQLite connection.
    """
    cursor = connection.execute(_REBUILD_JOBS_TABLE_INFO_QUERY)
    existing_columns = {row[1] for row in cursor}

    NEW_COLUMNS = {
        "execution_id": "ALTER TABLE rebuild_jobs ADD COLUMN execution_id TEXT",
        "checkpoint_data": "ALTER TABLE rebuild_jobs ADD COLUMN checkpoint_data TEXT",
    }

    for col_name, alter_statement in NEW_COLUMNS.items():
        if col_name not in existing_columns:
            connection.execute(alter_statement)  # noqa: S3649


def _apply_upgrade_004_cancellation_columns(connection: sqlite3.Connection) -> None:
    """
    Apply migration 004 (add cancellation columns) conditionally and update status constraints.

    Args:
        connection: SQLite connection.
    """
    cursor = connection.execute(_REBUILD_JOBS_TABLE_INFO_QUERY)
    existing_columns = {row[1] for row in cursor}

    # If the column already exists, we assume the migration has run.
    if "cancellation_requested_at" in existing_columns:
        return

    # Turn off foreign keys temporarily for the table swap
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        # 1. Create the new table with the updated CHECK constraint
        connection.execute(f"""
            CREATE TABLE rebuild_jobs_new (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                source TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_ms INTEGER,
                node_count INTEGER,
                edge_count INTEGER,
                sanitized_failure_category TEXT,
                sanitized_failure_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                active_worker_id TEXT,
                last_heartbeat_at TEXT,
                execution_id TEXT,
                checkpoint_data TEXT,
                cancellation_requested_at TEXT,
                CONSTRAINT ck_rebuild_jobs_status CHECK (
                    status IN ({_REBUILD_JOB_STATUS_LITERALS})
                )
            )
            """)

        # 2. Build the list of columns to copy (those that exist in both)
        target_columns = {
            "job_id",
            "status",
            "requested_by",
            "source",
            "started_at",
            "completed_at",
            "duration_ms",
            "node_count",
            "edge_count",
            "sanitized_failure_category",
            "sanitized_failure_message",
            "created_at",
            "updated_at",
            "active_worker_id",
            "last_heartbeat_at",
            "execution_id",
            "checkpoint_data",
        }
        cols_to_copy_list = [c for c in existing_columns if c in target_columns]
        cols_to_copy = ", ".join(f'"{c}"' for c in cols_to_copy_list)

        # 3. Copy data
        query_template = "INSERT INTO rebuild_jobs_new ({}) SELECT {} FROM rebuild_jobs"
        query = query_template.replace("{}", cols_to_copy)
        connection.execute(query)

        # 4. Swap tables
        connection.execute("DROP TABLE rebuild_jobs")
        connection.execute("ALTER TABLE rebuild_jobs_new RENAME TO rebuild_jobs")
        # 5. Recreate indexes that were lost with the original table
        connection.execute("CREATE INDEX IF NOT EXISTS ix_rebuild_jobs_created_at ON rebuild_jobs (created_at)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_rebuild_jobs_status_created_at ON rebuild_jobs (status, created_at)"
        )

    finally:
        # Always turn foreign keys back on
        connection.execute("PRAGMA foreign_keys=ON")


# ---------------------------------------------------------------------------
# Private helpers for apply_postgresql_heartbeat_migration
# ---------------------------------------------------------------------------


def _inspect_rebuild_jobs_columns(inspector: Inspector) -> tuple[list[str], dict[str, dict]]:
    """
    Return missing-column statements and metadata for bounded identifiers.

    Scans rebuild_jobs columns once and produces:
    - The list of ADD COLUMN IF NOT EXISTS statements needed for missing
      heartbeat columns.
    - The SQLAlchemy column metadata dict for active_worker_id, or None
      if the column does not yet exist.

    Args:
        inspector: SQLAlchemy inspector instance.

    Returns:
        tuple[list[str], dict | None]: A tuple containing the list of SQL statements and
            optional column metadata.
    """
    columns = inspector.get_columns("rebuild_jobs")
    existing: set[str] = set()
    identifier_columns: dict[str, dict] = {}
    for col in columns:
        name = col["name"]
        existing.add(name)
        if name in _REBUILD_IDENTIFIER_COLUMNS:
            identifier_columns[name] = col

    statements: list[str] = []
    if "active_worker_id" not in existing:
        statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS active_worker_id VARCHAR(64)")
    if "last_heartbeat_at" not in existing:
        statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ")
    if "execution_id" not in existing:
        statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS execution_id VARCHAR(64)")
    if "checkpoint_data" not in existing:
        statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS checkpoint_data TEXT")
    if "cancellation_requested_at" not in existing:
        statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS cancellation_requested_at TIMESTAMPTZ")
    return statements, identifier_columns


def _identifier_declared_incompatible(column: dict | None) -> bool:
    """Check whether a present identifier column is unbounded or wider than 64.

    Return True when the identifier is unbounded or wider than VARCHAR(64).

    Safety is determined only by the authoritative in-transaction re-check in
    _apply_normalization_in_transaction(), after taking an exclusive lock.

    Args:
        column (dict | None): SQLAlchemy column metadata dict.

    Returns:
        bool: True if the column is unbounded or wider than 64 characters.
    """
    if column is None:
        return False
    col_length = getattr(column.get("type"), "length", None)
    return col_length is None or col_length > 64


def _apply_normalization_in_transaction(connection, columns_to_normalize: tuple[str, ...]) -> None:
    """
    Attempt to narrow migration-owned identifier columns to `VARCHAR(64)`.

    Acquires one exclusive lock, re-checks each requested column's maximum
    stored length, and narrows only columns whose data fits.

    Parameters:
        connection: An active SQLAlchemy transactional connection bound to the target PostgreSQL database.
        columns_to_normalize: Trusted migration-owned identifier column names.
    """
    if not columns_to_normalize:
        return

    connection.execute(text("LOCK TABLE rebuild_jobs IN ACCESS EXCLUSIVE MODE"))
    for column_name in columns_to_normalize:
        recheck = connection.execute(text(f"SELECT MAX(LENGTH({column_name})) FROM rebuild_jobs")).scalar()
        if recheck is None or recheck <= 64:
            connection.execute(text(f"ALTER TABLE rebuild_jobs ALTER COLUMN {column_name} TYPE VARCHAR(64)"))
            continue
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="migration_width_normalization_skipped",
                message=(f"Skipping {column_name} width normalization: max length={recheck} exceeds 64 (re-check)"),
                metadata={"column": column_name, "max_length": recheck},
            ),
        )


def _apply_postgresql_status_constraint_update(connection) -> None:
    """
    Ensure the PostgreSQL status check constraint includes all supported statuses.

    This is necessary because PostgreSQL does not support simple ALTER TABLE
    to add values to a CHECK constraint. We drop and recreate it.
    """
    # 1. Drop existing constraint if it exists
    connection.execute(text("ALTER TABLE rebuild_jobs DROP CONSTRAINT IF EXISTS ck_rebuild_jobs_status"))

    # 2. Add the updated constraint
    status_constraint_sql = f"""
        ALTER TABLE rebuild_jobs ADD CONSTRAINT ck_rebuild_jobs_status
            CHECK (status IN ({_REBUILD_JOB_STATUS_LITERALS}))
    """
    connection.execute(text(status_constraint_sql))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_postgresql_heartbeat_migration(engine: Engine) -> None:
    """
    Ensure heartbeat columns exist for PostgreSQL rebuild_jobs tables.

    This is an idempotent compatibility migration used during startup for
    existing PostgreSQL databases that predate heartbeat tracking columns.

    Args:
        engine: SQLAlchemy Engine instance for the target database.
    """
    inspector = inspect(engine)
    if "rebuild_jobs" not in inspector.get_table_names():
        return

    statements, identifier_columns = _inspect_rebuild_jobs_columns(inspector)
    columns_to_normalize = tuple(
        column_name
        for column_name in _REBUILD_IDENTIFIER_COLUMNS
        if _identifier_declared_incompatible(identifier_columns.get(column_name))
    )

    if not statements and not columns_to_normalize:
        # Still attempt to update the constraint even if columns are present,
        # as the constraint might be outdated (e.g. from an earlier 5C.X PR).
        with engine.begin() as connection:
            _apply_postgresql_status_constraint_update(connection)
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        _apply_normalization_in_transaction(connection, columns_to_normalize)
        _apply_postgresql_status_constraint_update(connection)


def postgresql_heartbeat_schema_gaps(inspector: Inspector) -> list[str]:
    """Return PostgreSQL rebuild compatibility gaps without changing the schema."""
    if "rebuild_jobs" not in inspector.get_table_names():
        return ["rebuild_jobs table"]

    required_columns = {
        "active_worker_id",
        "last_heartbeat_at",
        "execution_id",
        "checkpoint_data",
        "cancellation_requested_at",
    }
    columns = {column["name"]: column for column in inspector.get_columns("rebuild_jobs")}
    gaps = [f"rebuild_jobs.{name}" for name in sorted(required_columns - set(columns))]

    for column_name in _REBUILD_IDENTIFIER_COLUMNS:
        column = columns.get(column_name)
        if column is None:
            continue
        length = getattr(column.get("type"), "length", None)
        if length is None or length > 64:
            gaps.append(f"rebuild_jobs.{column_name} width <= 64")

    supported_statuses = set(REBUILD_JOB_STATUSES)
    status_constraint = next(
        (
            constraint
            for constraint in inspector.get_check_constraints("rebuild_jobs")
            if constraint.get("name") == "ck_rebuild_jobs_status"
        ),
        None,
    )
    sql_text = str(status_constraint.get("sqltext", "")) if status_constraint else ""
    status_literals = set(re.findall(r"'([^']+)'", sql_text))
    if not status_constraint or "status" not in sql_text.lower() or status_literals != supported_statuses:
        gaps.append("ck_rebuild_jobs_status")
    return gaps
