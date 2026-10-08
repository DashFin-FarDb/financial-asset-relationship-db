"""Live PostgreSQL verification for runtime capability SQL construction."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from api import database as api_database
from src.data import database as runtime_database

pytestmark = pytest.mark.integration

_BOOTSTRAP_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_database_capability_roles.sql"


def _postgres_test_url() -> str:
    """Return the explicit PostgreSQL integration-test URL or skip the test."""
    url = os.getenv("FARDB_POSTGRES_TEST_URL") or os.getenv("FARDB_EPHEMERAL_POSTGRES_URL")
    if not url:
        pytest.skip("Neither FARDB_POSTGRES_TEST_URL nor FARDB_EPHEMERAL_POSTGRES_URL is configured")
    assert url is not None
    if not url.lower().startswith(("postgresql://", "postgres://")):
        pytest.fail("Configured PostgreSQL test URL must be a PostgreSQL URL")
    return url


def _ensure_bootstrap_roles(url: str) -> None:
    """Ensure capability roles are present before testing SQL verifiers."""
    if not _BOOTSTRAP_PATH.exists():
        return
    import psycopg2

    bootstrap_sql = _BOOTSTRAP_PATH.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(bootstrap_sql)
    finally:
        conn.close()


def test_runtime_capability_verifier_sql_executes_against_postgres() -> None:
    """Execute the real verifier SQL against PostgreSQL rather than only mocking it."""
    url = _postgres_test_url()
    try:
        _ensure_bootstrap_roles(url)
    except Exception:  # noqa: BLE001
        pass

    engine = create_engine(url, future=True)
    try:
        raw_connection = engine.raw_connection()
        try:
            cursor = raw_connection.cursor()
            try:
                cursor.execute(
                    api_database._AUTH_SAFE_ROLE_SQL,
                    (
                        api_database.AUTH_RUNTIME_ROLE,
                        list(api_database._NON_AUTH_MANAGED_TABLES),
                        list(api_database._NON_AUTH_MANAGED_TABLES),
                        list(
                            runtime_database.get_approved_login_principals(
                                api_database.AUTH_RUNTIME_ROLE,
                            )
                        ),
                    ),
                )
                assert cursor.fetchone() is not None

                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
            finally:
                cursor.close()
        finally:
            raw_connection.close()

        with engine.connect() as connection:
            capabilities = (runtime_database.GRAPH_RUNTIME_CAPABILITY,)
            runtime_database._verify_runtime_capability_roles(
                connection,
                capabilities,
                runtime_database._managed_table_names(capabilities),
            )
    finally:
        engine.dispose()
