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
from typing import Final, Optional

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


def _get_database_url() -> Optional[str]:
    """
    Get database URL from env vars
    (prefer ASSET_GRAPH..., fallback DATABASE_URL).
    """
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


def _redact_url_dsn(dsn: str) -> Optional[str]:
    """Redact URL-style DSN credentials if present."""
    if "://" not in dsn or "@" not in dsn:
        return None
    scheme, rest = dsn.split("://", 1)
    creds_and_host = rest.split("@", 1)
    if len(creds_and_host) != 2:
        return None
    return f"{scheme}://***:***@{creds_and_host[1]}"


def _redact_keyword_dsn(dsn: str) -> Optional[str]:
    """Redact password=... segment in keyword-style DSN."""
    if "password=" not in dsn.lower():
        return None
    parts = dsn.split()
    redacted_parts = ["password=***" if part.lower().startswith("password=") else part for part in parts]
    return " ".join(redacted_parts)


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
    if any(token in database_url for token in PLACEHOLDER_TOKENS):
        pytest.skip("Database URL contains a placeholder password token")
    if database_url.strip().lower().startswith("sqlite"):
        pytest.skip("Database URL is SQLite; Postgres connectivity test not applicable")
    return database_url


def _run_smoke_query(database_url: str):
    """Run a lightweight Postgres smoke query and return one row."""
    try:
        with connect(database_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version();")
            return cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to connect to Postgres using DSN={_redact_dsn(database_url)}: {exc}")


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
    row = _run_smoke_query(database_url)

    assert row is not None  # nosec B101
    assert len(row) == 3  # nosec B101
    assert isinstance(row[0], str) and row[0]  # nosec B101
    assert isinstance(row[1], str) and row[1]  # nosec B101
    assert isinstance(row[2], str) and row[2]  # nosec B101
