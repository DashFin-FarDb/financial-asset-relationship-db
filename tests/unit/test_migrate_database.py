"""Tests for the explicit database migration operator command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import scripts.migrate_database as migrate_database
from src.config.settings import Settings


def test_migrate_configured_databases_owns_all_mutating_setup(monkeypatch) -> None:
    """One command should migrate graph/coordination and provision auth state."""
    test_password = "-".join(("strong", "test", "password"))
    settings = Settings(
        secret_key="s" * 32,
        asset_graph_database_url="sqlite:///graph.db",
        database_url="sqlite:///auth.db",
        coordination_database_url="sqlite:///coordination.db",
        admin_username="admin",
        admin_password=test_password,
    )
    engines = {
        "sqlite:///graph.db": MagicMock(),
        "sqlite:///coordination.db": MagicMock(),
    }
    initialize_schema = MagicMock()
    seed_credentials = MagicMock()
    verify_auth = MagicMock()
    init_db = MagicMock()
    verify_graph = MagicMock()

    monkeypatch.setattr(migrate_database, "initialize_schema", initialize_schema)
    monkeypatch.setattr(migrate_database, "_seed_credentials_from_settings", seed_credentials)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", verify_auth)
    monkeypatch.setattr(migrate_database.user_repository, "has_users", lambda: True)
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_graph)
    monkeypatch.setattr(migrate_database, "API_DATABASE_URL", settings.database_url)

    migrated = migrate_database.migrate_configured_databases(
        settings,
        engine_factory=lambda url: engines[url],
    )

    assert migrated == ("graph", "coordination", "auth")
    assert init_db.call_count == 2
    assert verify_graph.call_count == 2
    initialize_schema.assert_called_once_with()
    seed_credentials.assert_called_once_with(migrate_database.user_repository, settings)
    verify_auth.assert_called_once_with()
    for engine in engines.values():
        engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_requires_provisioned_credentials(monkeypatch) -> None:
    """An auth-only setup must fail if it cannot establish a usable credential."""
    settings = Settings(secret_key="s" * 32, database_url="sqlite:///auth.db")
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "_seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database.user_repository, "has_users", lambda: False)
    monkeypatch.setattr(migrate_database, "API_DATABASE_URL", settings.database_url)
    monkeypatch.setattr(migrate_database, "init_db", lambda _engine: None)
    monkeypatch.setattr(migrate_database, "verify_database_schema", lambda _engine: None)

    try:
        migrate_database.migrate_configured_databases(settings, engine_factory=lambda _url: MagicMock())
    except RuntimeError as exc:
        assert "credential provisioning incomplete" in str(exc)
    else:
        raise AssertionError("migration command accepted an empty credential store")


def test_migrate_configured_databases_migrates_coordination_without_graph(monkeypatch) -> None:
    """An explicitly configured coordination target must not depend on graph persistence."""
    settings = Settings(
        secret_key="s" * 32,
        database_url="sqlite:///auth.db",
        coordination_database_url="sqlite:///coordination.db",
    )
    coordination_engine = MagicMock()
    monkeypatch.setattr(migrate_database, "API_DATABASE_URL", settings.database_url)
    monkeypatch.setattr(migrate_database, "init_db", MagicMock())
    monkeypatch.setattr(migrate_database, "verify_database_schema", MagicMock())
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "_seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database.user_repository, "has_users", lambda: True)

    migrated = migrate_database.migrate_configured_databases(
        settings,
        engine_factory=lambda _url: coordination_engine,
    )

    assert migrated == ("coordination", "auth")
    coordination_engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_rejects_auth_target_mismatch(monkeypatch) -> None:
    """An injected settings object must not silently operate on an import-time auth target."""
    settings = Settings(secret_key="s" * 32, database_url="sqlite:///requested.db")
    monkeypatch.setattr(migrate_database, "API_DATABASE_URL", "sqlite:///initialized.db")

    with pytest.raises(RuntimeError, match="does not match"):
        migrate_database.migrate_configured_databases(settings)
