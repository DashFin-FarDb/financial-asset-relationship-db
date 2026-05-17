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
import sqlite3
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

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
    Apply all pending SQL migrations to a SQLite database.

    This function is SQLite-specific and will not work with PostgreSQL or other databases.
    For non-SQLite databases, use Alembic or implement backend-specific migrations.

    This function applies migrations in order:
    1. 001_initial.sql - Base schema (idempotent via IF NOT EXISTS)
    2. 002_add_heartbeat_columns.sql - Upgrade migration (applied conditionally)

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        ValueError: If db_path is not a valid SQLite database path.
    """
    db_path = Path(db_path)
    # migrations/ is at repository root, not under src/
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    from contextlib import closing

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            # Migration 001: Base schema (always safe to run, uses IF NOT EXISTS)
            _apply_sql_migration(connection, migrations_dir / "001_initial.sql")

            # Migration 002: Add heartbeat columns (conditional, check first)
            _apply_upgrade_002_heartbeat_columns(connection)


# ---------------------------------------------------------------------------
# Private helpers for apply_postgresql_heartbeat_migration
# ---------------------------------------------------------------------------

def _inspect_rebuild_jobs_columns(inspector) -> tuple[list[str], dict | None]:
    """
    Return (add_column_statements, active_worker_col_meta).

    Scans rebuild_jobs columns once and produces:
    - The list of ADD COLUMN IF NOT EXISTS statements needed for missing
      heartbeat columns.
    - The SQLAlchemy column metadata dict for active_worker_id, or None
      if the column does not yet exist.
    """
    columns = inspector.get_columns("rebuild_jobs")
    existing: set[str] = set()
    active_worker_col = None
    for col in columns:
        name = col["name"]
        existing.add(name)
        if name == "active_worker_id":
            active_worker_col = col

    statements: list[str] = []
    if "active_worker_id" not in existing:
        statements.append(
            "ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS active_worker_id VARCHAR(64)"
        )
    if "last_heartbeat_at" not in existing:
        statements.append(
            "ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ"
        )
    return statements, active_worker_col


def _check_width_normalization_needed(engine: Engine, active_worker_col: dict | None) -> bool:
    """
    Return True when active_worker_id is wider than VARCHAR(64) and all
    existing values safely fit within 64 characters.

    The MAX(LENGTH(...)) query is a read-only pre-check executed *outside*
    the DDL transaction so the result can gate the ALTER COLUMN statement.
    """
    if active_worker_col is None:
        return False
    col_length = getattr(active_worker_col.get("type"), "length", None)
    if not (isinstance(col_length, int) and col_length > 64):
        return False

    with engine.connect() as conn:
        max_length = conn.execute(
            text("SELECT MAX(LENGTH(active_worker_id)) FROM rebuild_jobs")
        ).scalar()

    if max_length is None or max_length <= 64:
        return True

    logger.warning(
        "Skipping active_worker_id width normalization: max length=%s exceeds 64",
        max_length,
    )
    return False


def _apply_normalization_in_transaction(connection, needs_width_normalization: bool) -> None:
    """
    Conditionally narrow active_worker_id to VARCHAR(64) inside an open
    DDL transaction, with a re-check to close the race window.
    """
    if not needs_width_normalization:
        return

    recheck = connection.execute(
        text("SELECT MAX(LENGTH(active_worker_id)) FROM rebuild_jobs")
    ).scalar()
    if recheck is None or recheck <= 64:
        connection.execute(
            text("ALTER TABLE rebuild_jobs ALTER COLUMN active_worker_id TYPE VARCHAR(64)")
        )
    else:
        logger.warning(
            "Skipping active_worker_id width normalization: max length=%s exceeds 64 (re-check)",
            recheck,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_postgresql_heartbeat_migration(engine: Engine) -> None:
    """
    Ensure heartbeat columns exist for PostgreSQL rebuild_jobs tables.

    This is an idempotent compatibility migration used during startup for
    existing PostgreSQL databases that predate heartbeat tracking columns.
    """
    inspector = inspect(engine)
    if "rebuild_jobs" not in inspector.get_table_names():
        return

    statements, active_worker_col = _inspect_rebuild_jobs_columns(inspector)
    needs_width_normalization = _check_width_normalization_needed(engine, active_worker_col)

    if not statements and not needs_width_normalization:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        _apply_normalization_in_transaction(connection, needs_width_normalization)
