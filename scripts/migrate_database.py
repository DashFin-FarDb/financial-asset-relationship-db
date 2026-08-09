"""Run the single explicit FarDB database migration authority path."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from api.auth import seed_credentials_from_settings, user_repository
from api.database import DATABASE_URL as API_DATABASE_URL
from api.database import initialize_schema, verify_schema_compatibility
from api.graph_lifecycle_providers import resolve_hosted_graph_database_url
from src.config.settings import Settings, load_settings
from src.data.database import create_engine_from_url, init_db, verify_database_schema


class DisposableEngine(Protocol):
    """Minimal engine behavior needed by this migration command."""

    def dispose(self) -> None:
        """Release any pooled database resources."""


def _configured_engines(
    settings: Settings,
    engine_factory: Callable[[str], DisposableEngine],
) -> tuple[str | None, dict[str, DisposableEngine]]:
    """Resolve each configured graph authority target exactly once."""
    graph_url = resolve_hosted_graph_database_url(settings)
    engines = {graph_url: engine_factory(graph_url)} if graph_url else {}
    coordination_url = settings.coordination_database_url
    if coordination_url and coordination_url not in engines:
        engines[coordination_url] = engine_factory(coordination_url)
    return graph_url, engines


def _require_auth_database_alignment(settings: Settings) -> None:
    """Prevent explicit settings from targeting a different auth database global."""
    configured_url = settings.database_url
    if not configured_url or configured_url.strip() != API_DATABASE_URL.strip():
        raise RuntimeError("configured auth database does not match the initialized API database target")


def migrate_configured_databases(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], DisposableEngine] = create_engine_from_url,
) -> tuple[str, ...]:
    """Apply configured graph/coordination/auth setup through operator authority.

    Existing environment precedence and database abstractions are intentionally
    preserved. Operators run this command with migration-owner credentials,
    then start the application with its restricted runtime credentials.
    """
    resolved_settings = settings or load_settings()
    _require_auth_database_alignment(resolved_settings)
    migrated: list[str] = []
    graph_url, engines = _configured_engines(resolved_settings, engine_factory)

    try:
        for url, engine in engines.items():
            init_db(engine)
            verify_database_schema(engine)
            migrated.append("graph" if url == graph_url else "coordination")

        initialize_schema()
        seed_credentials_from_settings(user_repository, resolved_settings)
        verify_schema_compatibility()
        if not user_repository.has_users():
            raise RuntimeError(
                "credential provisioning incomplete: configure ADMIN_USERNAME and ADMIN_PASSWORD "
                "or provision a user before running the application"
            )
        migrated.append("auth")
        return tuple(migrated)
    finally:
        for engine in engines.values():
            engine.dispose()


def main() -> int:
    """Run configured migrations and emit only non-sensitive component names."""
    migrated = migrate_configured_databases()
    print("Database migration complete: " + ", ".join(migrated))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
