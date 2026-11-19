"""SQLite compatibility tests for adding nullable valuation metrics to existing databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.data.migrations import apply_migrations


def test_valuation_metric_migration_upgrades_legacy_database_idempotently(tmp_path: Path) -> None:
    """Legacy SQLite schemas gain optional metrics without changing existing rows."""
    db_path = tmp_path / "legacy-valuation.db"
    migration_001 = Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(migration_001.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO assets (id, symbol, name, asset_class, sector, price, currency) "
            "VALUES ('LEGACY', 'LEG', 'Legacy Equity', 'Equity', 'Technology', 10.0, 'USD')"
        )
        connection.execute(
            "INSERT INTO rebuild_jobs (job_id, requested_by, status, created_at, updated_at) "
            "VALUES ('LEGACY-JOB', 'test', 'pending', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        connection.execute(
            "CREATE TABLE relationship_projection_publications " "(id TEXT PRIMARY KEY, published_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO relationship_projection_publications (id, published_at) "
            "VALUES ('LEGACY-PUBLICATION', '2026-01-01T00:00:00Z')"
        )
        connection.commit()

    apply_migrations(db_path)
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as connection:
        asset_columns = {row[1] for row in connection.execute("PRAGMA table_info(assets)")}
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(rebuild_jobs)")}
        row = connection.execute(
            "SELECT id, forward_pe_ratio, peg_ratio, price_to_sales_ratio, price_to_book_ratio, "
            "eps_growth_next_year, eps_growth_next_5_years FROM assets WHERE id = 'LEGACY'"
        ).fetchone()
        version_default = connection.execute(
            "SELECT snapshot_attestation_version FROM rebuild_jobs WHERE job_id = 'LEGACY-JOB'"
        ).fetchone()
        publication_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(relationship_projection_publications)")
        }
        publication_version = connection.execute(
            "SELECT snapshot_attestation_version FROM relationship_projection_publications "
            "WHERE id = 'LEGACY-PUBLICATION'"
        ).fetchone()

    assert {
        "forward_pe_ratio",
        "peg_ratio",
        "price_to_sales_ratio",
        "price_to_book_ratio",
        "eps_growth_next_year",
        "eps_growth_next_5_years",
    } <= asset_columns
    assert "snapshot_attestation_version" in job_columns
    assert row == ("LEGACY", None, None, None, None, None, None)
    assert version_default == ("v1",)
    assert "snapshot_attestation_version" in publication_columns
    assert publication_version == ("v1",)
