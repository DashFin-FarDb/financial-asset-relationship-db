"""
Integration test for PostgreSQL connectivity.

This test is intentionally opt-in because it requires real credentials and a live
database. By default it will be skipped in CI and local runs.

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

from psycopg2 import connect  # noqa: E402  # pylint: disable=wrong-import-position

PLACEHOLDER_TOKENS: Final[tuple[str, ...]] = (
    "[YOUR-PASSWORD]",
    "<PASSWORD>",
    "YOUR_PASSWORD",
)


def _get_database_url() -> Optional[str]:
    """Get the database URL from env vars (prefer ASSET_GRAPH..., fallback DATABASE_URL)."""
    # Prefer the same env var used by the app. Fall back for legacy/local usage.
    return os.getenv("ASSET_GRAPH_DATABASE_URL") or os.getenv("DATABASE_URL")


def _redact_dsn(dsn: str) -> str:
    """
    Return a redacted connection string suitable for logs.

    We avoid leaking credentials. This is deliberately conservative and does not
    attempt to parse every DSN format perfectly; it only aims to avoid printing
    secrets.
    """
    # Common URL form: postgresql://user:pass@host:port/db
    if "://" in dsn and "@" in dsn:
        scheme, rest = dsn.split("://", 1)
        # Use rsplit to handle '@' characters within the password
        creds_and_host = rest.rsplit("@", 1)
        if len(creds_and_host) == 2:
            return f"{scheme}://***:***@{creds_and_host[1]}"
    # psycopg2 keyword DSN: "dbname=... user=... password=... host=..."
    # Redact 'password=' segment if present.
    lowered = dsn.lower()
    if "password=" in lowered:
        parts = dsn.split()
        redacted_parts: list[str] = []
        for part in parts:
            if part.lower().startswith("password="):
                redacted_parts.append("password=***")
            else:
                redacted_parts.append(part)
        return " ".join(redacted_parts)
    return "***"


@pytest.mark.integration
def test_postgres_connection_smoke() -> None:
    """
    Smoke-test a live Postgres connection.

    This is opt-in. It will be skipped unless RUN_POSTGRES_TESTS=1 is set.

    Expectations:
    - Connection succeeds
    - A trivial query returns a row
    """
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip(
            "Set RUN_POSTGRES_TESTS=1 to enable live Postgres connectivity test"
        )

    database_url = _get_database_url()
    if not database_url:
        pytest.skip(
            "No database URL provided. Set ASSET_GRAPH_DATABASE_URL (preferred) or DATABASE_URL."
        )

    if any(token in database_url for token in PLACEHOLDER_TOKENS):
        pytest.skip("Database URL contains a placeholder password token")

    # Defensive check: avoid accidentally running against SQLite URL.
    if database_url.strip().lower().startswith("sqlite"):
        pytest.skip("Database URL is SQLite; Postgres connectivity test not applicable")

    try:
        with connect(database_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version();")
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"Failed to connect to Postgres using DSN={_redact_dsn(database_url)}: {exc}"
        )

    assert row is not None  # nosec B101
    assert len(row) == 3  # nosec B101
    assert isinstance(row[0], str) and row[0]  # nosec B101
    assert isinstance(row[1], str) and row[1]  # nosec B101
    assert isinstance(row[2], str) and row[2]  # nosec B101
