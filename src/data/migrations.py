"""Database migration utilities for schema evolution."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


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
        _apply_upgrade_002_heartbeat_columns(connection, migrations_dir / "002_add_heartbeat_columns.sql")


def _apply_sql_migration(connection: sqlite3.Connection, migration_file: Path) -> None:
    """
    Apply a SQL migration script.

    Args:
        connection: SQLite connection.
        migration_file: Path to the SQL file.
    """
    sql = migration_file.read_text(encoding="utf-8")
    connection.executescript(sql)


def _apply_upgrade_002_heartbeat_columns(connection: sqlite3.Connection, migration_file: Path) -> None:
    """
    Apply migration 002 (add heartbeat columns) conditionally.

    Checks if columns exist before running ALTER TABLE statements,
    since SQLite's ALTER TABLE ADD COLUMN is not idempotent.

    Args:
        connection: SQLite connection.
        migration_file: Path to the SQL file.
    """
    # Check which columns already exist
    cursor = connection.execute("PRAGMA table_info(rebuild_jobs)")
    existing_columns = {row[1] for row in cursor}

    columns_to_add = [
        ("active_worker_id", "TEXT"),
        ("last_heartbeat_at", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            connection.execute(f"ALTER TABLE rebuild_jobs ADD COLUMN {col_name} {col_type}")
            connection.commit()
