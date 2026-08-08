"""Run the single explicit FarDB database migration authority path."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.engine import Engine

from api.auth import _seed_credentials_from_settings, user_repository
from api.database import initialize_schema, verify_schema_compatibility
from api.graph_lifecycle_providers import resolve_hosted_graph_database_url
from src.config.settings import Settings, load_settings
from src.data.database import create_engine_from_url, init_db, verify_database_schema


def migrate_configured_databases(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] = create_engine_from_url,
) -> tuple[str, ...]:
    """Apply configured graph/coordination/auth setup through operator authority.

    Existing environment precedence and database abstractions are intentionally
    preserved. Operators run this command with migration-owner credentials,
    then start the application with its restricted runtime credentials.
    """
    resolved_settings = settings or load_settings()
    migrated: list[str] = []
    engines: dict[str, Engine] = {}

    graph_url = resolve_hosted_graph_database_url(resolved_settings)
    if graph_url:
        engines[graph_url] = engine_factory(graph_url)

    coordination_url = resolved_settings.coordination_database_url
    if graph_url and coordination_url and coordination_url not in engines:
        engines[coordination_url] = engine_factory(coordination_url)

    try:
        for url, engine in engines.items():
            init_db(engine)
            verify_database_schema(engine)
            migrated.append("graph" if url == graph_url else "coordination")

        initialize_schema()
        _seed_credentials_from_settings(user_repository, resolved_settings)
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
