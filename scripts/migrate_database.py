"""Run the single explicit FarDB database migration authority path."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.engine import Engine

from api.auth import seed_credentials_from_settings, user_repository
from api.database import (
    bind_database_url,
    ensure_runtime_access,
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


def _is_postgresql_url(url: str) -> bool:
    """Return whether a configured URL selects PostgreSQL without connecting."""
    normalized = url.strip().lower()
    return normalized.startswith("postgresql://") or normalized.startswith("postgres://")


def _configured_database_urls(settings: Settings) -> dict[str, str]:
    """Resolve configured logical targets in stable component order."""
    auth_url = settings.database_url
    if not auth_url:
        raise RuntimeError("configured auth database is missing")
    graph_url = resolve_hosted_graph_database_url(settings)
    coordination_url = settings.coordination_database_url or graph_url
    configured = {"auth": auth_url}
    if graph_url:
        configured["graph"] = graph_url
    if coordination_url:
        configured["coordination"] = coordination_url
    return configured


def _resolve_postgresql_plan(database_urls: dict[str, str]):
    """Validate manifest, bindings, identity, and aliases before any execution."""
    postgresql_urls = {
        logical_target: database_url
        for logical_target, database_url in database_urls.items()
        if _is_postgresql_url(database_url)
    }
    if not postgresql_urls:
        return None, ()
    binding_value = os.environ.get(TARGET_BINDINGS_ENV)
    if not binding_value:
        raise TargetIdentityError()
    manifest = load_and_validate_manifest()
    plan = resolve_target_plan(Path(binding_value), manifest, postgresql_urls)
    for target in plan:
        assert_profile_write_allowed(target)
    return manifest, plan


def _configured_engines(
    settings: Settings,
    engine_factory: Callable[[str], Engine],
) -> tuple[str | None, dict[str, tuple[Engine, set[str]]]]:
    """Resolve each target once and retain every capability required on it."""
    graph_url = resolve_hosted_graph_database_url(settings)
    configured: dict[str, set[str]] = {}
    if graph_url:
        configured.setdefault(graph_url, set()).add(GRAPH_RUNTIME_CAPABILITY)
    coordination_url = settings.coordination_database_url or graph_url
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
    if manifest is not None:
        for target in postgresql_plan:
            apply_profile_to_database(target, manifest)

    _graph_url, engines = _configured_engines(resolved_settings, engine_factory)

    try:
        for _url, (engine, capabilities) in engines.items():
            if not _is_postgresql_url(str(engine.url)):
                init_db(engine)
            verify_database_schema(engine, required_capabilities=capabilities)

        with bind_database_url(auth_url):
            if _is_postgresql_url(auth_url):
                verify_schema_compatibility()
                verify_runtime_access_catalog()
            else:
                initialize_schema()
            seed_credentials_from_settings(user_repository, resolved_settings)
            if not _is_postgresql_url(auth_url):
                ensure_runtime_access()
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
    except CapabilityRoleBootstrapRequiredError as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - sanitize dependency and DSN-bearing failures
        print(f"Database migration failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("Database migration complete: " + ", ".join(migrated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
