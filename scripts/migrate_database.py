"""Run the single explicit FarDB database migration authority path."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError

from api.auth import seed_credentials_from_settings, user_repository
from api.database import (
    bind_database_url,
    fetch_value,
    initialize_schema,
    verify_runtime_access_catalog,
    verify_schema_compatibility,
)
from api.graph_lifecycle_providers import resolve_hosted_graph_database_url
from scripts.postgresql_ledger import (
    TARGET_BINDINGS_ENV,
    TARGET_IDENTITY_INDETERMINATE,
    HostedWriteBarrierError,
    LedgerManifest,
    PlannedTarget,
    TargetIdentityError,
    apply_profile_to_database,
    assert_profile_write_allowed,
    load_and_validate_manifest,
    resolve_target_plan,
)
from src.config.settings import Settings, load_settings
from src.data.database import (
    COORDINATION_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_CAPABILITY,
    CapabilityRoleBootstrapRequiredError,
    create_engine_from_url,
    init_db,
    verify_database_schema,
)


class PostgreSQLPlanApplyError(RuntimeError):
    """Report bounded progress when one target in a multi-target plan fails."""

    def __init__(self, completed_profiles: tuple[str, ...], failed_profile: str) -> None:
        """Retain only reviewed profile names, never URLs or dependency output."""
        self.completed_profiles = completed_profiles
        self.failed_profile = failed_profile
        super().__init__("PostgreSQL profile application did not complete")


def _is_postgresql_url(url: str) -> bool:
    """Return whether a configured URL selects PostgreSQL without connecting."""
    scheme, separator, _remainder = url.strip().lower().partition("://")
    return bool(separator) and (scheme in ("postgres", "postgresql") or scheme.startswith(("postgres+", "postgresql+")))


def _operator_binding_path(value: str) -> Path:
    """Require an explicit absolute, non-symlink operator control-file path."""
    candidate = Path(value)
    if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_file():
        raise TargetIdentityError()
    return candidate


def _postgresql_cli_url(value: str) -> str:
    """Strip a SQLAlchemy driver suffix for the Supabase CLI without hiding credentials."""
    parsed = make_url(value)
    if parsed.get_backend_name() not in ("postgres", "postgresql"):
        raise ValueError("configured URL is not PostgreSQL")
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)


def _auth_binding_url(value: str) -> str:
    """Return a DB-API-compatible auth URL while preserving SQLite targets."""
    return _postgresql_cli_url(value) if _is_postgresql_url(value) else value


def _configured_database_urls(settings: Settings) -> dict[str, str]:
    """Resolve configured logical targets in stable component order."""
    auth_url = settings.database_url
    if not auth_url:
        raise RuntimeError("configured auth database is missing")
    graph_url = resolve_hosted_graph_database_url(settings)
    coordination_url = settings.coordination_database_url or graph_url
    # Settings preserves DATABASE_URL as a local coordination fallback. Without
    # a graph target that is an implicit auth-only default, not an unsupported
    # two-component PostgreSQL alias.
    if graph_url is None and coordination_url == auth_url:
        coordination_url = None
    configured = {"auth": auth_url}
    if graph_url:
        configured["graph"] = graph_url
    if coordination_url:
        configured["coordination"] = coordination_url
    return configured


def _resolve_postgresql_plan(
    database_urls: dict[str, str],
) -> tuple[LedgerManifest | None, tuple[PlannedTarget, ...]]:
    """Validate manifest, bindings, identity, and aliases before any execution."""
    try:
        postgresql_urls = {
            logical_target: _postgresql_cli_url(database_url)
            for logical_target, database_url in database_urls.items()
            if _is_postgresql_url(database_url)
        }
    except (ArgumentError, TypeError, ValueError) as exc:
        raise TargetIdentityError() from exc
    if not postgresql_urls:
        return None, ()
    binding_value = os.environ.get(TARGET_BINDINGS_ENV)
    if not binding_value:
        raise TargetIdentityError()
    manifest = load_and_validate_manifest()
    plan = resolve_target_plan(_operator_binding_path(binding_value), manifest, postgresql_urls)
    for target in plan:
        assert_profile_write_allowed(target)
    return manifest, plan


def _configured_engines(
    database_urls: dict[str, str],
    engine_factory: Callable[[str], Engine],
) -> tuple[str | None, dict[str, tuple[Engine, set[str]]]]:
    """Resolve each target once and retain every capability required on it."""
    graph_url = database_urls.get("graph")
    configured: dict[str, set[str]] = {}
    if graph_url:
        configured.setdefault(graph_url, set()).add(GRAPH_RUNTIME_CAPABILITY)
    coordination_url = database_urls.get("coordination")
    if coordination_url:
        configured.setdefault(coordination_url, set()).add(COORDINATION_RUNTIME_CAPABILITY)

    engines: dict[str, tuple[Engine, set[str]]] = {}
    try:
        for url, capabilities in configured.items():
            engines[url] = (engine_factory(url), capabilities)
    except Exception:
        for engine, _capabilities in engines.values():
            engine.dispose()
        raise
    return graph_url, engines


def _has_usable_credentials() -> bool:
    """Return whether an enabled credential has a supported password hash."""
    return bool(
        fetch_value(
            "SELECT 1 FROM user_credentials WHERE disabled = 0 AND hashed_password LIKE ? LIMIT 1",
            ("$pbkdf2-sha256$%",),
        )
    )


def _apply_postgresql_plan(
    manifest: LedgerManifest | None,
    plan: tuple[PlannedTarget, ...],
) -> None:
    """Apply a preflighted plan while retaining only bounded progress metadata."""
    if manifest is None:
        return
    completed_profiles: list[str] = []
    for target in plan:
        try:
            apply_profile_to_database(target, manifest)
        except Exception as exc:  # noqa: BLE001 - every target failure must retain bounded partial progress
            raise PostgreSQLPlanApplyError(tuple(completed_profiles), target.profile) from exc
        completed_profiles.append(target.profile)


def migrate_configured_databases(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] = create_engine_from_url,
) -> tuple[str, ...]:
    """Apply configured graph/coordination/auth setup through operator authority.

    PostgreSQL targets are validated and deduplicated by protected identity before
    any engine, connection, or subprocess starts. Their schema is applied only by
    an exact disposable projection of the selected Supabase ledger profile. SQLite
    retains the existing local development initialization path.
    """
    resolved_settings = settings or load_settings()
    database_urls = _configured_database_urls(resolved_settings)
    auth_url = database_urls["auth"]

    # This protected gate must complete before engine_factory or the CLI is called.
    manifest, postgresql_plan = _resolve_postgresql_plan(database_urls)
    _apply_postgresql_plan(manifest, postgresql_plan)

    _graph_url, engines = _configured_engines(database_urls, engine_factory)

    try:
        for _url, (engine, capabilities) in engines.items():
            if not _is_postgresql_url(str(engine.url)):
                init_db(engine)
            verify_database_schema(engine, required_capabilities=capabilities)

        with bind_database_url(_auth_binding_url(auth_url)):
            if _is_postgresql_url(auth_url):
                verify_schema_compatibility()
                verify_runtime_access_catalog()
            else:
                initialize_schema()
            seed_credentials_from_settings(user_repository, resolved_settings)
            if not _is_postgresql_url(auth_url):
                verify_schema_compatibility()
            if not _has_usable_credentials():
                raise RuntimeError(
                    "credential provisioning incomplete: configure ADMIN_USERNAME and ADMIN_PASSWORD "
                    "or provision a user before running the application"
                )
        return tuple(
            component
            for component in ("graph", "coordination", "auth")
            if component == "auth" or component in database_urls
        )
    finally:
        for engine, _capabilities in engines.values():
            engine.dispose()


def main() -> int:
    """Run configured migrations and emit only non-sensitive component names."""
    try:
        migrated = migrate_configured_databases()
    except TargetIdentityError:
        print(f"Database migration failed: {TARGET_IDENTITY_INDETERMINATE}", file=sys.stderr)
        return 1
    except HostedWriteBarrierError:
        print("Database migration failed: PostgreSQL hosted write barrier blocked execution", file=sys.stderr)
        return 1
    except PostgreSQLPlanApplyError as exc:
        completed = ",".join(exc.completed_profiles) if exc.completed_profiles else "none"
        print(
            "Database migration failed: PostgreSQL profile application incomplete "
            f"(completed={completed}; failed={exc.failed_profile})",
            file=sys.stderr,
        )
        return 1
    except CapabilityRoleBootstrapRequiredError as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        return 1
    # This boundary sanitizes dependency failures that could contain DSNs.
    except Exception as exc:  # noqa: BLE001
        print(f"Database migration failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("Database migration complete: " + ", ".join(migrated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
