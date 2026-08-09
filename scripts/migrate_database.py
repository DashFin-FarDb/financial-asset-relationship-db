"""Run the single explicit FarDB database migration authority path."""

from __future__ import annotations

import sys
from collections.abc import Callable

from sqlalchemy.engine import Engine

from api.auth import seed_credentials_from_settings, user_repository
from api.database import (
    bind_database_url,
    ensure_runtime_access,
    fetch_value,
    initialize_schema,
    verify_schema_compatibility,
)
from api.graph_lifecycle_providers import resolve_hosted_graph_database_url
from src.config.settings import Settings, load_settings
from src.data.database import (
    COORDINATION_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_CAPABILITY,
    create_engine_from_url,
    ensure_runtime_database_capabilities,
    init_db,
    verify_database_schema,
)


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
            "SELECT 1 FROM user_credentials "
            "WHERE disabled = 0 AND hashed_password LIKE ? LIMIT 1",
            ("$pbkdf2-sha256$%",),
        )
    )


def migrate_configured_databases(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] = create_engine_from_url,
) -> tuple[str, ...]:
    """Apply configured graph/coordination/auth setup through operator authority.

    Existing environment precedence and database abstractions are intentionally
    preserved. Operators run this command with migration-owner credentials,
    then start the application with its restricted runtime credentials. Capability
    selection controls the installed runtime grants and RLS policies; ``init_db``
    deliberately installs the shared structural schema even for a coordination-only
    target.
    """
    resolved_settings = settings or load_settings()
    auth_url = resolved_settings.database_url
    if not auth_url:
        raise RuntimeError("configured auth database is missing")

    migrated: list[str] = []
    _graph_url, engines = _configured_engines(resolved_settings, engine_factory)

    try:
        for _url, (engine, capabilities) in engines.items():
            init_db(engine)
            ensure_runtime_database_capabilities(engine, capabilities)
            verify_database_schema(engine, required_capabilities=capabilities)
            if GRAPH_RUNTIME_CAPABILITY in capabilities:
                migrated.append("graph")
            if COORDINATION_RUNTIME_CAPABILITY in capabilities:
                migrated.append("coordination")

        with bind_database_url(auth_url):
            initialize_schema()
            seed_credentials_from_settings(user_repository, resolved_settings)
            ensure_runtime_access()
            verify_schema_compatibility()
            if not _has_usable_credentials():
                raise RuntimeError(
                    "credential provisioning incomplete: configure ADMIN_USERNAME and ADMIN_PASSWORD "
                    "or provision a user before running the application"
                )
        migrated.append("auth")
        return tuple(migrated)
    finally:
        for engine, _capabilities in engines.values():
            engine.dispose()


def main() -> int:
    """Run configured migrations and emit only non-sensitive component names."""
    try:
        migrated = migrate_configured_databases()
    except Exception as exc:  # noqa: BLE001 - sanitize dependency and DSN-bearing failures
        print(f"Database migration failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("Database migration complete: " + ", ".join(migrated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
