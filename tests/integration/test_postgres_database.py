"""
Integration test for PostgreSQL connectivity.

This test is intentionally opt-in because it requires real credentials.
It also requires a live database and is skipped in CI/local runs by default.

Enable explicitly by setting:
  RUN_POSTGRES_TESTS=1
and providing one of:
  ASSET_GRAPH_DATABASE_URL (preferred)
  DATABASE_URL

Security:
- We never print the full DSN.
- We skip if a placeholder password token is present.
"""

from __future__ import annotations

import os
from typing import Final, cast

import pytest

pytest.importorskip("psycopg2")

# pyright: ignore[reportMissingModuleSource]
# pylint: disable=wrong-import-position,import-error
from psycopg2 import connect  # noqa: E402  # type: ignore[import-untyped]

# pylint: enable=wrong-import-position,import-error

PLACEHOLDER_TOKENS: Final[tuple[str, ...]] = (
    "[YOUR-PASSWORD]",
    "<PASSWORD>",
    "YOUR_PASSWORD",
)


def _get_database_url() -> str | None:
    """Get database URL from env vars (prefer ASSET_GRAPH..., fallback DATABASE_URL)."""
    # Prefer the same env var used by the app.
    # Fall back for legacy/local usage.
    return os.getenv("ASSET_GRAPH_DATABASE_URL") or os.getenv("DATABASE_URL")


def _redact_dsn(dsn: str) -> str:
    """
    Return a redacted connection string suitable for logs.

    We avoid leaking credentials. This is deliberately conservative
    and does not
    attempt to parse every DSN format perfectly; it only aims to avoid printing
    secrets.
    """
    url_redaction = _redact_url_dsn(dsn)
    if url_redaction is not None:
        return url_redaction
    keyword_redaction = _redact_keyword_dsn(dsn)
    if keyword_redaction is not None:
        return keyword_redaction
    return "***"


def _redact_url_dsn(dsn: str) -> str | None:
    """Redact URL-style DSN credentials if present."""
    if "://" not in dsn or "@" not in dsn:
        return None
    scheme, rest = dsn.split("://", 1)
    creds_and_host = rest.split("@", 1)
    if len(creds_and_host) != 2:
        return None
    return f"{scheme}://***:***@{creds_and_host[1]}"


def _redact_keyword_dsn(dsn: str) -> str | None:
    """Redact password=... segment in keyword-style DSN."""
    if "password=" not in dsn.lower():
        return None
    parts = dsn.split()
    redacted_parts = ["password=***" if part.lower().startswith("password=") else part for part in parts]
    return " ".join(redacted_parts)


def _row_value(row: object, key: str | None = None, index: int = 0) -> object:
    """
    Extract a value from a database row that may be dict-like or tuple/list-like.

    Args:
        row: The database row (dict, tuple, list, or other row type)
        key: Optional key for dict-like access
        index: Index for tuple/list-like access (default: 0)

    Returns:
        The value at the specified key or index
    """
    # Try dict-like access first if key is provided
    if key is not None and hasattr(row, "__getitem__") and isinstance(row, dict):
        return row[key]
    # Fall back to index-based access for tuples/lists
    if hasattr(row, "__getitem__"):
        return row[index]  # type: ignore[index]
    raise TypeError(f"Cannot extract value from row type: {type(row)}")


def _ensure_live_test_enabled() -> None:
    """Skip test unless live Postgres integration tests are enabled."""
    if os.getenv("RUN_POSTGRES_TESTS") == "1":
        return
    pytest.skip("Set RUN_POSTGRES_TESTS=1 to enable live Postgres connectivity test")


def _read_validated_database_url() -> str:
    """Read DB URL and skip on missing placeholder/SQLite values."""
    database_url = _get_database_url()
    if not database_url:
        pytest.skip("No database URL provided. Set ASSET_GRAPH_DATABASE_URL (preferred) or DATABASE_URL.")

    assert database_url is not None
    if any(token in database_url for token in PLACEHOLDER_TOKENS):
        pytest.skip("Database URL contains a placeholder password token")
    if database_url.strip().lower().startswith("sqlite"):
        pytest.skip("Database URL is SQLite; Postgres connectivity test not applicable")
    return database_url


def _run_smoke_query(database_url: str) -> object:
    """Run a lightweight Postgres smoke query and return one row."""
    try:
        with connect(database_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version();")
            return cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to connect to Postgres using DSN={_redact_dsn(database_url)}: {exc}")
        # pytest.fail is expected to raise and not return, but add an explicit
        # raise to avoid any implicit fall-through in static analysis.
        raise AssertionError(f"Failed to connect to Postgres using DSN={_redact_dsn(database_url)}: {exc}") from exc


@pytest.mark.integration
def test_postgres_connection_smoke() -> None:
    """
    Smoke-test a live Postgres connection.

    This is opt-in. It will be skipped unless RUN_POSTGRES_TESTS=1 is set.

    Expectations:
    - Connection succeeds
    - A trivial query returns a row
    """
    _ensure_live_test_enabled()
    database_url = _read_validated_database_url()
    row = cast("tuple[str, str, str]", _run_smoke_query(database_url))

    assert row is not None  # nosec B101
    assert len(row) == 3  # nosec B101

    database_name, database_user, postgres_version = row

    assert isinstance(database_name, str) and database_name  # nosec B101
    assert isinstance(database_user, str) and database_user  # nosec B101
    assert isinstance(postgres_version, str) and postgres_version  # nosec B101


@pytest.mark.integration
def test_restricted_runtime_role_verifies_schema_on_cold_start_and_restart() -> None:
    """A separately configured app role must verify twice without migration authority."""
    _ensure_live_test_enabled()
    runtime_url = os.getenv("FARDB_RUNTIME_DATABASE_URL")
    if not runtime_url:
        pytest.skip("Set FARDB_RUNTIME_DATABASE_URL to the restricted application-role DSN")
    assert runtime_url is not None
    if any(token in runtime_url for token in PLACEHOLDER_TOKENS):
        pytest.skip("Runtime database URL contains a placeholder password token")

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    from src.data.database import verify_database_schema, verify_runtime_database_authority

    engine = create_engine(runtime_url, future=True)
    try:
        with engine.connect() as connection:
            role_posture = connection.execute(
                text(
                    "SELECT role.rolsuper, "
                    "has_schema_privilege(current_user, current_schema(), 'CREATE'), "
                    "COUNT(table_rel.oid) FILTER (WHERE table_rel.relowner = role.oid) "
                    "FROM pg_roles AS role "
                    "LEFT JOIN pg_class AS table_rel ON table_rel.relname IN "
                    "('assets', 'rebuild_jobs', 'relationship_assertions', 'user_credentials') "
                    "AND table_rel.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = current_schema()) "
                    "WHERE role.rolname = current_user GROUP BY role.rolsuper, role.oid"
                )
            ).one()
        assert role_posture == (False, False, 0)

        verify_database_schema(engine)
        verify_runtime_database_authority(engine)

        with engine.connect() as connection:
            assert connection.execute(text("SELECT to_regclass('user_credentials')")).scalar_one() is not None

        forbidden_statements = (
            "CREATE TABLE cq_runtime_authority_probe (id INTEGER)",
            "GRANT SELECT ON assets TO PUBLIC",
            "INSERT INTO user_credentials "
            "(username, hashed_password, disabled) VALUES ('cq-runtime-probe', 'not-used', 1)",
        )
        for statement in forbidden_statements:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    with pytest.raises(DBAPIError):
                        connection.execute(text(statement))
                finally:
                    transaction.rollback()

        engine.dispose()
        engine = create_engine(runtime_url, future=True)
        verify_database_schema(engine)
        verify_runtime_database_authority(engine)
    finally:
        engine.dispose()
