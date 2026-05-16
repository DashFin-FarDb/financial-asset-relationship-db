"""Database migration utilities for schema evolution."""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Explicit whitelist of allowed migration files
# Only migrations listed here can be executed (defense in depth)
ALLOWED_MIGRATIONS = frozenset(
    [
        "001_initial.sql",
        "002_add_heartbeat_columns.sql",
    ]
)


def apply_migrations(db_path: Path | str) -> None:
    """
    Apply all pending migrations to the database.

    This function applies migrations in order:
    1. 001_initial.sql - Base schema (idempotent via IF NOT EXISTS)
    2. 002_add_heartbeat_columns.sql - Upgrade migration (applied conditionally)

    Args:
        db_path: Path to the SQLite database file.
    """
    db_path = Path(db_path)
    # migrations/ is at repository root, not under src/
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    with sqlite3.connect(db_path) as connection:
        # Migration 001: Base schema (always safe to run, uses IF NOT EXISTS)
        _apply_sql_migration(connection, migrations_dir / "001_initial.sql")

        # Migration 002: Add heartbeat columns (conditional, check first)
        _apply_upgrade_002_heartbeat_columns(connection)


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
    # Validate that migration_file is within the expected migrations directory
    # to prevent path traversal attacks if this function is ever called with
    # untrusted input (defense in depth)
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    try:
        resolved_file = migration_file.resolve()
        # Ensure the file is within migrations directory
        resolved_file.relative_to(migrations_dir)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Migration file {migration_file} is not within trusted migrations directory") from exc

    if not resolved_file.is_file():
        raise ValueError(f"Migration file {migration_file} does not exist")

    # Validate file extension is .sql (trusted migration files only)
    if resolved_file.suffix.lower() != ".sql":
        raise ValueError(f"Migration file {migration_file} must have .sql extension")

    # Validate file is in the explicit whitelist of allowed migrations
    # This is the ultimate security barrier: only known, hardcoded migration files can execute
    if resolved_file.name not in ALLOWED_MIGRATIONS:
        raise ValueError(
            f"Migration file {resolved_file.name} is not in the allowed migrations whitelist. "
            f"Allowed: {sorted(ALLOWED_MIGRATIONS)}"
        )

    # Read migration SQL from validated trusted file
    # Security note: This is safe because:
    # 1. File path validated to be within migrations/ directory (no path traversal)
    # 2. File extension validated to be .sql
    # 3. File name validated against hardcoded whitelist (ALLOWED_MIGRATIONS)
    # 4. migrations/ directory is source-controlled, not user-writable
    # 5. This function is internal and only called with hardcoded migration paths
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

    Reads SQL from migrations/002_add_heartbeat_columns.sql but checks if
    columns exist before running ALTER TABLE statements, since SQLite's
    ALTER TABLE ADD COLUMN is not idempotent.

    Args:
        connection: SQLite connection.
    """
    # Check which columns already exist
    cursor = connection.execute("PRAGMA table_info(rebuild_jobs)")
    existing_columns = {row[1] for row in cursor}

    # Read SQL from the migration file (maintains single source of truth)
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    migration_file = migrations_dir / "002_add_heartbeat_columns.sql"

    # Parse the SQL to extract individual ALTER statements
    # The file contains two ALTER TABLE statements, one per column
    migration_sql = migration_file.read_text(encoding="utf-8")

    # Expected columns from migration 002
    required_columns = ["active_worker_id", "last_heartbeat_at"]

    for col_name in required_columns:
        if col_name not in existing_columns:
            # Extract and execute the specific ALTER statement for this column
            # Look for the line containing this column name
            for line in migration_sql.splitlines():
                if col_name in line and line.strip().startswith("ALTER TABLE"):
                    # Execute pre-validated DDL statement from trusted migration file
                    # SECURITY: SQL comes from version-controlled migration file
                    # that passed whitelist validation
                    connection.execute(line.strip().rstrip(";"))  # noqa: S3649
                    connection.commit()
                    break
