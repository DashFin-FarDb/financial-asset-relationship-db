"""Tests for the explicit database migration operator command."""

from __future__ import annotations

from contextlib import contextmanager
from typing import cast
from unittest.mock import MagicMock, call

import pytest

import scripts.migrate_database as migrate_database
from scripts.postgresql_ledger import (
    TARGET_BINDINGS_ENV,
    TARGET_IDENTITY_INDETERMINATE,
    HostedWriteBarrierError,
    PlannedTarget,
    TargetIdentityError,
    TargetProfileConflictError,
)
from src.config.settings import Settings
from src.data.database import CapabilityRoleBootstrapRequiredError

pytestmark = pytest.mark.unit


def _settings(**overrides) -> Settings:
    """Build minimal operator settings with caller-selected database URLs."""
    values = {
        "secret_key": "s" * 32,
        "database_url": "sqlite:///auth.db",
    }
    values.update(overrides)
    return Settings(**values)


def _engine(url: str) -> MagicMock:
    """Build a disposable engine double with a stable URL string."""
    engine = MagicMock()
    engine.url = url
    return engine


@contextmanager
def _null_binding(_url: str):
    """Provide a no-op API database binding for unit tests."""
    yield


def _stub_auth_success(monkeypatch) -> None:
    """Stub credential provisioning while preserving operator call boundaries."""
    monkeypatch.setattr(migrate_database, "bind_database_url", _null_binding)
    monkeypatch.setattr(migrate_database, "initialize_schema", MagicMock())
    monkeypatch.setattr(migrate_database, "verify_schema_compatibility", MagicMock())
    monkeypatch.setattr(migrate_database, "verify_runtime_access_catalog", MagicMock())
    monkeypatch.setattr(migrate_database, "ensure_runtime_access", MagicMock())
    monkeypatch.setattr(migrate_database, "seed_credentials_from_settings", MagicMock())
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: True)


def test_sqlite_operator_path_preserves_local_initialization(monkeypatch) -> None:
    """SQLite targets retain explicit local initialization and stable output order."""
    settings = _settings(
        asset_graph_database_url="sqlite:///graph.db",
        coordination_database_url="sqlite:///coordination.db",
        admin_username="admin",
        admin_password="strong-test-password",
    )
    engines = {
        "sqlite:///graph.db": _engine("sqlite:///graph.db"),
        "sqlite:///coordination.db": _engine("sqlite:///coordination.db"),
    }
    init_db = MagicMock()
    verify_schema = MagicMock()
    _stub_auth_success(monkeypatch)
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_schema)

    migrated = migrate_database.migrate_configured_databases(settings, engine_factory=lambda url: engines[url])

    assert migrated == ("graph", "coordination", "auth")
    assert init_db.call_count == 2
    assert verify_schema.call_args_list == [
        call(engines["sqlite:///graph.db"], required_capabilities={"graph"}),
        call(engines["sqlite:///coordination.db"], required_capabilities={"coordination"}),
    ]
    cast(MagicMock, migrate_database.initialize_schema).assert_called_once_with()
    cast(MagicMock, migrate_database.ensure_runtime_access).assert_called_once_with()
    cast(MagicMock, migrate_database.verify_runtime_access_catalog).assert_not_called()
    for engine in engines.values():
        engine.dispose.assert_called_once_with()


def test_postgresql_targets_apply_after_global_preflight_and_before_engines(monkeypatch, tmp_path) -> None:
    """All identities and barriers resolve before profile application or connection creation."""
    settings = _settings(
        database_url="postgresql://operator@localhost/auth",
        asset_graph_database_url="postgresql://operator@localhost/graph",
        coordination_database_url="postgresql://operator@localhost/coordination",
        admin_username="admin",
        admin_password="strong-test-password",
    )
    binding_path = tmp_path / "bindings.json"
    binding_path.write_text("{}", encoding="utf-8")
    binding_path.chmod(0o600)
    monkeypatch.setenv(TARGET_BINDINGS_ENV, str(binding_path))
    manifest = object()
    plan = tuple(
        PlannedTarget(
            logical_targets=(component,),
            profile=component,
            lineage="fresh-v1",
            execution_class="loopback",
            fingerprint=component[0] * 64,
            database_url=f"postgresql://operator@localhost/{component}",
        )
        for component in ("auth", "graph", "coordination")
    )
    events: list[str] = []
    monkeypatch.setattr(migrate_database, "load_and_validate_manifest", lambda: manifest)
    monkeypatch.setattr(migrate_database, "resolve_target_plan", lambda *_args: plan)
    monkeypatch.setattr(
        migrate_database,
        "assert_profile_write_allowed",
        lambda target: events.append(f"barrier:{target.profile}"),
    )
    monkeypatch.setattr(
        migrate_database,
        "apply_profile_to_database",
        lambda target, _manifest: events.append(f"apply:{target.profile}"),
    )
    engines = {
        plan[1].database_url: _engine(plan[1].database_url),
        plan[2].database_url: _engine(plan[2].database_url),
    }

    def engine_factory(url: str):
        events.append(f"engine:{url.rsplit('/', 1)[-1]}")
        return engines[url]

    _stub_auth_success(monkeypatch)
    verify_schema = MagicMock()
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_schema)
    monkeypatch.setattr(migrate_database, "init_db", MagicMock())

    migrated = migrate_database.migrate_configured_databases(settings, engine_factory=engine_factory)

    assert migrated == ("graph", "coordination", "auth")
    assert events[:3] == ["barrier:auth", "barrier:graph", "barrier:coordination"]
    assert events[3:6] == ["apply:auth", "apply:graph", "apply:coordination"]
    assert events[6:] == ["engine:graph", "engine:coordination"]
    cast(MagicMock, migrate_database.init_db).assert_not_called()
    assert verify_schema.call_args_list == [
        call(engines[plan[1].database_url], required_capabilities={"graph"}),
        call(engines[plan[2].database_url], required_capabilities={"coordination"}),
    ]
    cast(MagicMock, migrate_database.initialize_schema).assert_not_called()
    cast(MagicMock, migrate_database.ensure_runtime_access).assert_not_called()
    cast(MagicMock, migrate_database.verify_runtime_access_catalog).assert_called_once_with()
    assert cast(MagicMock, migrate_database.verify_schema_compatibility).call_count == 2


def test_missing_postgresql_binding_fails_before_engine_or_subprocess(monkeypatch) -> None:
    """PostgreSQL cannot run without a protected target identity document."""
    monkeypatch.delenv(TARGET_BINDINGS_ENV, raising=False)
    engine_factory = MagicMock()
    apply_profile = MagicMock()
    monkeypatch.setattr(migrate_database, "apply_profile_to_database", apply_profile)

    with pytest.raises(TargetIdentityError, match=TARGET_IDENTITY_INDETERMINATE):
        migrate_database.migrate_configured_databases(
            _settings(database_url="postgresql://operator@localhost/auth"),
            engine_factory=engine_factory,
        )

    engine_factory.assert_not_called()
    apply_profile.assert_not_called()


def test_target_profile_conflict_fails_before_engine_or_subprocess(monkeypatch, tmp_path) -> None:
    """A resolver conflict cannot be recovered by inferring a broader profile."""
    binding_path = tmp_path / "bindings.json"
    binding_path.write_text("{}", encoding="utf-8")
    binding_path.chmod(0o600)
    monkeypatch.setenv(TARGET_BINDINGS_ENV, str(binding_path))
    monkeypatch.setattr(migrate_database, "load_and_validate_manifest", lambda: object())
    monkeypatch.setattr(
        migrate_database,
        "resolve_target_plan",
        MagicMock(side_effect=TargetProfileConflictError("conflicting profiles")),
    )
    engine_factory = MagicMock()
    apply_profile = MagicMock()
    monkeypatch.setattr(migrate_database, "apply_profile_to_database", apply_profile)

    with pytest.raises(TargetProfileConflictError, match="conflicting profiles"):
        migrate_database.migrate_configured_databases(
            _settings(database_url="postgresql://operator@localhost/auth"),
            engine_factory=engine_factory,
        )

    engine_factory.assert_not_called()
    apply_profile.assert_not_called()


def test_all_write_barriers_run_before_first_profile_application(monkeypatch, tmp_path) -> None:
    """A later unsafe target cannot leave an earlier target partially applied."""
    binding_path = tmp_path / "bindings.json"
    binding_path.write_text("{}", encoding="utf-8")
    binding_path.chmod(0o600)
    monkeypatch.setenv(TARGET_BINDINGS_ENV, str(binding_path))
    safe = PlannedTarget(
        ("auth",),
        "auth",
        "fresh-v1",
        "loopback",
        "a" * 64,
        "postgresql://operator@localhost/auth",
    )
    unsafe = PlannedTarget(
        ("graph",),
        "graph",
        "fresh-v1",
        "hosted",
        "b" * 64,
        "postgresql://operator@project.supabase.co/postgres",
    )
    monkeypatch.setattr(migrate_database, "load_and_validate_manifest", lambda: object())
    monkeypatch.setattr(migrate_database, "resolve_target_plan", lambda *_args: (safe, unsafe))
    apply_profile = MagicMock()
    monkeypatch.setattr(migrate_database, "apply_profile_to_database", apply_profile)
    engine_factory = MagicMock()

    with pytest.raises(HostedWriteBarrierError):
        migrate_database.migrate_configured_databases(
            _settings(
                database_url=safe.database_url,
                asset_graph_database_url=unsafe.database_url,
                coordination_database_url="sqlite:///coordination.db",
            ),
            engine_factory=engine_factory,
        )

    apply_profile.assert_not_called()
    engine_factory.assert_not_called()


def test_shared_sqlite_graph_and_coordination_verify_once_with_union(monkeypatch) -> None:
    """A shared local target is initialized once with explicit combined capabilities."""
    shared_url = "sqlite:///shared.db"
    settings = _settings(asset_graph_database_url=shared_url)
    shared_engine = _engine(shared_url)
    _stub_auth_success(monkeypatch)
    init_db = MagicMock()
    verify_schema = MagicMock()
    monkeypatch.setattr(migrate_database, "init_db", init_db)
    monkeypatch.setattr(migrate_database, "verify_database_schema", verify_schema)

    migrated = migrate_database.migrate_configured_databases(settings, engine_factory=lambda _url: shared_engine)

    assert migrated == ("graph", "coordination", "auth")
    init_db.assert_called_once_with(shared_engine)
    verify_schema.assert_called_once_with(shared_engine, required_capabilities={"graph", "coordination"})
    shared_engine.dispose.assert_called_once_with()


def test_missing_auth_fails_before_other_targets(monkeypatch) -> None:
    """A missing auth target must fail before any engine or profile execution."""
    engine_factory = MagicMock()
    apply_profile = MagicMock()
    monkeypatch.setattr(migrate_database, "apply_profile_to_database", apply_profile)

    with pytest.raises(RuntimeError, match="configured auth database is missing"):
        migrate_database.migrate_configured_databases(
            _settings(database_url=None, coordination_database_url="sqlite:///coordination.db"),
            engine_factory=engine_factory,
        )

    engine_factory.assert_not_called()
    apply_profile.assert_not_called()


def test_requires_usable_credentials(monkeypatch) -> None:
    """Auth provisioning remains incomplete without an enabled supported password hash."""
    _stub_auth_success(monkeypatch)
    monkeypatch.setattr(migrate_database, "_has_usable_credentials", lambda: False)

    with pytest.raises(RuntimeError, match="credential provisioning incomplete"):
        migrate_database.migrate_configured_databases(_settings())


def test_configured_engines_disposes_partial_construction_on_failure() -> None:
    """A later engine-construction failure disposes every earlier engine."""
    settings = _settings(
        asset_graph_database_url="sqlite:///graph.db",
        coordination_database_url="sqlite:///coordination.db",
    )
    first_engine = _engine("sqlite:///graph.db")
    engine_factory = MagicMock(side_effect=[first_engine, RuntimeError("engine factory failed")])

    with pytest.raises(RuntimeError, match="engine factory failed"):
        migrate_database._configured_engines(settings, engine_factory)  # pylint: disable=protected-access

    first_engine.dispose.assert_called_once_with()


def test_main_sanitizes_dependency_errors(monkeypatch, capsys) -> None:
    """The CLI boundary never echoes a DSN-bearing dependency error."""
    secret_dsn = "postgresql://operator:not-a-credential@database.invalid/fardb"
    monkeypatch.setattr(
        migrate_database,
        "migrate_configured_databases",
        MagicMock(side_effect=RuntimeError(f"connection failed for {secret_dsn}")),
    )

    assert migrate_database.main() == 1
    captured = capsys.readouterr()
    assert "Database migration failed (RuntimeError)" in captured.err
    assert secret_dsn not in captured.err


def test_main_emits_fixed_target_identity_reason(monkeypatch, capsys) -> None:
    """Indeterminate protected identity has one non-sensitive public diagnostic."""
    monkeypatch.setattr(
        migrate_database,
        "migrate_configured_databases",
        MagicMock(side_effect=TargetIdentityError()),
    )

    assert migrate_database.main() == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == f"Database migration failed: {TARGET_IDENTITY_INDETERMINATE}"


def test_main_emits_bounded_hosted_barrier_reason(monkeypatch, capsys) -> None:
    """Hosted-write denial does not echo its URL or protected inputs."""
    monkeypatch.setattr(
        migrate_database,
        "migrate_configured_databases",
        MagicMock(side_effect=HostedWriteBarrierError("secret target detail")),
    )

    assert migrate_database.main() == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "Database migration failed: PostgreSQL hosted write barrier blocked execution"
    assert "secret target detail" not in captured.err


def test_main_reports_safe_capability_bootstrap_diagnostic(monkeypatch, capsys) -> None:
    """The legacy public exception retains a bounded bootstrap action diagnostic."""
    monkeypatch.setattr(
        migrate_database,
        "migrate_configured_databases",
        MagicMock(side_effect=CapabilityRoleBootstrapRequiredError("fardb_runtime_graph")),
    )

    assert migrate_database.main() == 1
    captured = capsys.readouterr()
    assert "required PostgreSQL capability role fardb_runtime_graph is missing" in captured.err
    assert "bootstrap_database_capability_roles.sql as a PostgreSQL superuser" in captured.err
