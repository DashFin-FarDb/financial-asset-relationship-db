"""Live PostgreSQL verification for runtime capability SQL construction."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

from api import database as api_database
from src.data import database as runtime_database

pytestmark = pytest.mark.integration


def _postgres_test_url() -> str:
    """Return the explicit PostgreSQL integration-test URL or skip the test."""
    url = os.getenv("FARDB_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("FARDB_POSTGRES_TEST_URL is not configured")
    if not url.lower().startswith(("postgresql://", "postgres://")):
        pytest.fail("FARDB_POSTGRES_TEST_URL must be a PostgreSQL URL")
    return url


def test_runtime_capability_verifier_sql_executes_against_postgres() -> None:
    """Execute the real verifier SQL against PostgreSQL rather than only mocking it."""
    engine = create_engine(_postgres_test_url(), future=True)
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
