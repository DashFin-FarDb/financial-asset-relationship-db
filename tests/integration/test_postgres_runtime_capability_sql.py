"""Live PostgreSQL verification for runtime capability SQL construction."""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine

from api import database as api_database
from src.data import database as runtime_database

pytestmark = pytest.mark.integration

_BOOTSTRAP_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_database_capability_roles.sql"
_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_TEST_POSTGRES_URL = "FARDB_POSTGRES_TEST_URL"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _postgres_test_url() -> str:
    """Return the explicitly opted-in, loopback-only disposable PostgreSQL URL or skip the test."""
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        pytest.skip(f"Set {_EPHEMERAL_AUTHORITY_FLAG}=1 only for disposable PostgreSQL authority tests")

    url = os.getenv(_EPHEMERAL_POSTGRES_URL)
    if not url:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} is required when {_EPHEMERAL_AUTHORITY_FLAG}=1")
    if not url.lower().startswith(("postgresql://", "postgres://")):
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} must be a PostgreSQL URL")

    test_url = os.getenv(_TEST_POSTGRES_URL)
    if test_url and test_url != url:
        pytest.fail(f"{_TEST_POSTGRES_URL} must match {_EPHEMERAL_POSTGRES_URL} for this mutating integration test")
    if urlsplit(url).hostname not in _LOOPBACK_HOSTS:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} must target a loopback PostgreSQL service")

    return url


def _drop_logins(
    url: str,
    created_logins: list[str],
    created_memberships: list[tuple[str, str]],
) -> None:
    """Revoke test-added memberships and drop only login roles created by this test."""
    if not created_logins and not created_memberships:
        return

    import psycopg2
    from psycopg2 import sql

    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            for capability_role, login_role in created_memberships:
                cursor.execute(
                    sql.SQL("REVOKE {} FROM {}").format(
                        sql.Identifier(capability_role),
                        sql.Identifier(login_role),
                    )
                )
            for login_role in created_logins:
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login_role)))
    finally:
        conn.close()


def _ensure_bootstrap_roles(url: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Ensure capability roles are present only on the explicitly opted-in disposable service."""
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1" or url != os.getenv(_EPHEMERAL_POSTGRES_URL):
        pytest.fail("Capability-role bootstrap is restricted to the opted-in FARDB_EPHEMERAL_POSTGRES_URL")

    if not _BOOTSTRAP_PATH.exists():
        return [], []

    import psycopg2
    from psycopg2 import sql

    created_logins: list[str] = []
    created_memberships: list[tuple[str, str]] = []
    bootstrap_sql = _BOOTSTRAP_PATH.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(bootstrap_sql)
            for login_role, capability_role in (
                ("fardb_login_auth", api_database.AUTH_RUNTIME_ROLE),
                ("fardb_login_graph", runtime_database.GRAPH_RUNTIME_ROLE),
            ):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (login_role,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
                        ).format(sql.Identifier(login_role))
                    )
                    created_logins.append(login_role)

                cursor.execute(
                    "SELECT 1 FROM pg_auth_members AS membership "
                    "JOIN pg_roles AS capability ON capability.oid = membership.roleid "
                    "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                    "WHERE capability.rolname = %s AND grantee.rolname = %s",
                    (capability_role, login_role),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("GRANT {} TO {}").format(
                            sql.Identifier(capability_role),
                            sql.Identifier(login_role),
                        )
                    )
                    created_memberships.append((capability_role, login_role))
    except Exception:
        with suppress(Exception):
            _drop_logins(url, created_logins, created_memberships)
        raise
    finally:
        conn.close()

    return created_logins, created_memberships


def test_runtime_capability_verifier_sql_executes_against_postgres() -> None:
    """Execute the real verifier SQL against PostgreSQL rather than only mocking it."""
    url = _postgres_test_url()
    created_logins, created_memberships = _ensure_bootstrap_roles(url)
    engine = None
    try:
        engine = create_engine(url, future=True)
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
                assert cursor.fetchone() == (True,)

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
        verification_failed = sys.exc_info()[0] is not None
        try:
            try:
                if engine is not None:
                    engine.dispose()
            finally:
                _drop_logins(url, created_logins, created_memberships)
        except Exception:
            if not verification_failed:
                raise
