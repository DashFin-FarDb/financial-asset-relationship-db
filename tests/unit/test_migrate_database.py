"""Tests for the explicit database migration operator command."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, call

import pytest

import scripts.migrate_database as migrate_database
from src.config.settings import Settings
from src.data.database import SchemaCompatibilityError

pytestmark = pytest.mark.unit


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
    ensure_capabilities = MagicMock()
    ensure_auth = MagicMock()
    bound_targets: list[str] = []

    @contextmanager
    def bind_target(url: str):
        """Record and yield one temporary API database binding."""
        bound_targets.append(url)
        yield

    monkeypatch.setattr(migrate_database, "initialize_schema", initialize_schema)
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", seed_credentials)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", verify_auth)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: True)
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_graph)
    monkeypatch.setattr(migrate_database, "ensure_runtime_database_capabilities", ensure_capabilities)
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", ensure_auth)
    monkeypatch.setattr(migrate_database, "bind_database_url", bind_target)

    migrated = migrate_database.migrate_configured_databases(
        settings,
        engine_factory=lambda url: engines[url],
    )

    assert migrated == ("graph", "coordination", "auth")
    assert init_db.call_count == 2
    assert verify_graph.call_count == 4
    assert ensure_capabilities.call_count == 2
    initialize_schema.assert_called_once_with()
    seed_credentials.assert_called_once_with(migrate_database.user_repository, settings)
    ensure_auth.assert_called_once_with()
    verify_auth.assert_called_once_with()
    assert bound_targets == ["sqlite:///auth.db"]
    for engine in engines.values():
        engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_rejects_incompatible_structure_before_authority(monkeypatch) -> None:
    """Structural incompatibility must fail before runtime authority can be changed."""
    graph_url = "sqlite:///graph.db"
    settings = Settings(
        secret_key="s" * 32,
        asset_graph_database_url=graph_url,
        database_url="sqlite:///auth.db",
    )
    graph_engine = MagicMock()
    init_db = MagicMock()
    verify_graph = MagicMock(side_effect=SchemaCompatibilityError("incompatible pre-existing schema"))
    ensure_capabilities = MagicMock()
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_graph)
    monkeypatch.setattr(migrate_database, "ensure_runtime_database_capabilities", ensure_capabilities)

    with pytest.raises(SchemaCompatibilityError, match="incompatible pre-existing schema"):
        migrate_database.migrate_configured_databases(
            settings,
            engine_factory=lambda _url: graph_engine,
        )

    init_db.assert_called_once_with(graph_engine)
    verify_graph.assert_called_once_with(graph_engine)
    ensure_capabilities.assert_not_called()
    graph_engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_requires_provisioned_credentials(monkeypatch) -> None:
    """An auth-only setup must fail if it cannot establish a usable credential."""
    settings = Settings(secret_key="s" * 32, database_url="sqlite:///auth.db")
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", lambda: None)
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: False)
    monkeypatch.setattr(migrate_database, "init_db", lambda _engine: None)
    monkeypatch.setattr(migrate_database, "verify_database_schema", lambda _engine, **_kwargs: None)

    with pytest.raises(RuntimeError, match="credential provisioning incomplete"):
        migrate_database.migrate_configured_databases(settings, engine_factory=lambda _url: MagicMock())


def test_migrate_configured_databases_rejects_missing_auth_before_other_targets(monkeypatch) -> None:
    """A missing auth target must fail before graph/coordination engines can mutate."""
    settings = Settings(
        secret_key="s" * 32,
        database_url=None,
        coordination_database_url="sqlite:///coordination.db",
    )
    engine_factory = MagicMock()
    init_db = MagicMock()
    ensure_capabilities = MagicMock()
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "ensure_runtime_database_capabilities", ensure_capabilities)

    with pytest.raises(RuntimeError, match="configured auth database is missing"):
        migrate_database.migrate_configured_databases(settings, engine_factory=engine_factory)

    engine_factory.assert_not_called()
    init_db.assert_not_called()
    ensure_capabilities.assert_not_called()


def test_configured_engines_disposes_partial_construction_on_factory_failure() -> None:
    """A later engine-construction failure must dispose already-created engines."""
    settings = Settings(
        secret_key="s" * 32,
        asset_graph_database_url="sqlite:///graph.db",
        database_url="sqlite:///auth.db",
        coordination_database_url="sqlite:///coordination.db",
    )
    first_engine = MagicMock()
    engine_factory = MagicMock(side_effect=[first_engine, RuntimeError("engine factory failed")])

    with pytest.raises(RuntimeError, match="engine factory failed"):
        migrate_database._configured_engines(settings, engine_factory)  # pylint: disable=protected-access

    first_engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_migrates_coordination_without_graph(monkeypatch) -> None:
    """An explicitly configured coordination target must not depend on graph persistence."""
    settings = Settings(
        secret_key="s" * 32,
        database_url="sqlite:///auth.db",
        coordination_database_url="sqlite:///coordination.db",
    )
    coordination_engine = MagicMock()
    monkeypatch.setattr(migrate_database, "init_db", MagicMock())
    monkeypatch.setattr(migrate_database, "verify_database_schema", MagicMock())
    monkeypatch.setattr(migrate_database, "ensure_runtime_database_capabilities", MagicMock())
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", lambda: None)
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: True)

    migrated = migrate_database.migrate_configured_databases(
        settings,
        engine_factory=lambda _url: coordination_engine,
    )

    assert migrated == ("coordination", "auth")
    coordination_engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_combines_shared_graph_and_coordination_capabilities(monkeypatch) -> None:
    """A shared URL must be migrated once with both required runtime capabilities."""
    shared_url = "sqlite:///shared.db"
    settings = Settings(
        secret_key="s" * 32,
        database_url="sqlite:///auth.db",
        asset_graph_database_url=shared_url,
    )
    shared_engine = MagicMock()
    ensure_capabilities = MagicMock()
    verify_graph = MagicMock()
    monkeypatch.setattr(migrate_database, "init_db", MagicMock())
    monkeypatch.setattr(migrate_database, "ensure_runtime_database_capabilities", ensure_capabilities)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_graph)
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", lambda: None)
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: True)

    migrated = migrate_database.migrate_configured_databases(
        settings,
        engine_factory=lambda _url: shared_engine,
    )

    assert migrated == ("graph", "coordination", "auth")
    capabilities = ensure_capabilities.call_args.args[1]
    assert capabilities == {
        migrate_database.GRAPH_RUNTIME_CAPABILITY,
        migrate_database.COORDINATION_RUNTIME_CAPABILITY,
    }
    assert verify_graph.call_args_list == [
        call(shared_engine),
        call(shared_engine, required_capabilities=capabilities),
    ]
    shared_engine.dispose.assert_called_once_with()


def test_migrate_configured_databases_binds_auth_target_at_execution_time(monkeypatch) -> None:
    """Explicit settings must select auth after the migration module was imported."""
    settings = Settings(secret_key="s" * 32, database_url="sqlite:///requested.db")
    bound_targets: list[str] = []

    @contextmanager
    def bind_target(url: str):
        """Record and yield the auth target selected at execution time."""
        bound_targets.append(url)
        yield

    monkeypatch.setattr(migrate_database, "bind_database_url", bind_target)
    monkeypatch.setattr(migrate_database, "initialize_schema", lambda: None)
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", lambda: None)
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", lambda: None)
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", lambda *_args: None)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: True)

    assert migrate_database.migrate_configured_databases(settings) == ("auth",)
    assert bound_targets == ["sqlite:///requested.db"]


def test_main_sanitizes_dependency_errors(monkeypatch, capsys) -> None:
    """The CLI boundary must not echo driver messages that can contain DSNs."""
    secret_dsn = "postgresql://operator:secret@database.invalid/fardb"

    def fail_migration():
        """Raise a DSN-bearing dependency error for CLI redaction coverage."""
        raise RuntimeError(f"connection failed for {secret_dsn}")

    monkeypatch.setattr(migrate_database, "migrate_configured_databases", fail_migration)

    assert migrate_database.main() == 1
    captured = capsys.readouterr()
    assert "Database migration failed (RuntimeError)" in captured.err
    assert secret_dsn not in captured.err
