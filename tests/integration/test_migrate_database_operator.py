"""Integration coverage for the explicit migration operator on real SQLite files."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import create_engine, inspect

from scripts.migrate_database import migrate_configured_databases
from src.config.settings import Settings

pytestmark = pytest.mark.integration


def test_coordination_only_migration_keeps_shared_structural_schema(tmp_path) -> None:
    """Coordination-only authority still migrates the shared structural schema."""
    coordination_path = tmp_path / "coordination.db"
    auth_path = tmp_path / "auth.db"
    settings = Settings(
        secret_key="s" * 32,
        database_url=f"sqlite:///{auth_path}",
        coordination_database_url=f"sqlite:///{coordination_path}",
        admin_username="admin",
        admin_password="strong-test-password",
    )

    assert migrate_configured_databases(settings) == ("coordination", "auth")

    engine = create_engine(f"sqlite:///{coordination_path}", future=True)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {"distributed_locks", "assets", "relationship_assertions"}.issubset(tables)


def test_migration_rejects_store_with_only_disabled_user(tmp_path) -> None:
    """A disabled credential must not satisfy the migration provisioning postcondition."""
    auth_path = tmp_path / "disabled-auth.db"
    settings = Settings(
        secret_key="s" * 32,
        database_url=f"sqlite:///{auth_path}",
        admin_username="disabled-admin",
        admin_password="strong-test-password",
        admin_disabled=True,
    )

    with pytest.raises(RuntimeError, match="credential provisioning incomplete"):
        migrate_configured_databases(settings)

    with closing(sqlite3.connect(auth_path)) as connection:
        row = connection.execute(
            "SELECT disabled, hashed_password FROM user_credentials WHERE username = ?",
            ("disabled-admin",),
        ).fetchone()

    assert row is not None
    assert row[0] == 1
    assert str(row[1]).startswith("$pbkdf2-sha256$")
