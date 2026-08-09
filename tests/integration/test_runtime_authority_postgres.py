"""Ephemeral-PostgreSQL regressions for runtime authority verification.

These tests create temporary roles and alter object ownership. They must run only
against the dedicated disposable PostgreSQL service in CI, never against staging
or another provider database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import sql  # noqa: E402  # type: ignore[import-untyped]
from sqlalchemy import create_engine  # noqa: E402

from src.data.database import (  # noqa: E402
    SchemaCompatibilityError,
    init_db,
    verify_runtime_database_authority,
)

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_AUTH_RUNTIME_LOGIN = "cq1608_auth_runtime"
_AUTH_WRITE_ROLE = "cq1608_auth_writer"
_AUTH_REPLICATION_ROLE = "cq1608_auth_replication"
_SEQUENCE_RUNTIME_LOGIN = "cq1608_sequence_runtime"
_SEQUENCE_OWNER_ROLE = "cq1608_sequence_owner"


def _ephemeral_database_url() -> str:
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        pytest.skip(f"Set {_EPHEMERAL_AUTHORITY_FLAG}=1 only for disposable PostgreSQL authority tests")
    database_url = os.getenv("ASSET_GRAPH_DATABASE_URL")
    if not database_url or not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Disposable PostgreSQL authority tests require ASSET_GRAPH_DATABASE_URL")
    return database_url


@contextmanager
def _operator_connection(database_url: str) -> Iterator[object]:
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        yield connection
    finally:
        connection.close()


def _runtime_connection(database_url: str, role_name: str):
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role_name)))
    connection.autocommit = False
    return connection


def _drop_roles(database_url: str, *role_names: str) -> None:
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for role_name in role_names:
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


def _prepare_auth_schema(database_url: str) -> None:
    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.initialize_schema()


@pytest.mark.integration
@pytest.mark.parametrize("attack_role", ["replication", "credential_update"])
def test_auth_runtime_rejects_assumable_privileged_roles(attack_role: str) -> None:
    """NOINHERIT does not make a SET ROLE-reachable replication/write role safe."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    elevated_role = _AUTH_REPLICATION_ROLE if attack_role == "replication" else _AUTH_WRITE_ROLE
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(_AUTH_RUNTIME_LOGIN))
            )
            if attack_role == "replication":
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOBYPASSRLS REPLICATION"
                    ).format(sql.Identifier(elevated_role))
                )
            else:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOBYPASSRLS NOREPLICATION"
                    ).format(sql.Identifier(elevated_role))
                )
                cursor.execute(
                    sql.SQL("GRANT UPDATE (hashed_password) ON TABLE user_credentials TO {}").format(
                        sql.Identifier(elevated_role)
                    )
                )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(elevated_role),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )

        import api.database as api_database

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"),
        ):
            api_database.verify_runtime_authority()
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE UPDATE (hashed_password) ON TABLE user_credentials FROM {}").format(
                    sql.Identifier(_AUTH_WRITE_ROLE)
                )
            )
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, elevated_role)


@pytest.mark.integration
def test_runtime_database_authority_executes_against_linked_application_sequence() -> None:
    """Exercise the sequence-ownership catalog path against live PostgreSQL."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    init_db(operator_engine)

    original_owner: str | None = None
    runtime_engine = None
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'asset_relationships'::regclass")
            original_owner = cursor.fetchone()[0]
            assert isinstance(original_owner, str) and original_owner

            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(_SEQUENCE_OWNER_ROLE))
            )
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(_SEQUENCE_RUNTIME_LOGIN))
            )
            cursor.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE)))
            cursor.execute(
                sql.SQL("ALTER TABLE asset_relationships OWNER TO {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE))
            )
            cursor.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE)))
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_SEQUENCE_OWNER_ROLE),
                    sql.Identifier(_SEQUENCE_RUNTIME_LOGIN),
                )
            )

            cursor.execute(
                "SELECT pg_get_userbyid(relowner) FROM pg_class "
                "WHERE oid = pg_get_serial_sequence('asset_relationships', 'id')::regclass"
            )
            assert cursor.fetchone()[0] == _SEQUENCE_OWNER_ROLE
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_depend AS dependency "
                "WHERE dependency.classid = 'pg_class'::regclass "
                "AND dependency.refclassid = 'pg_class'::regclass "
                "AND dependency.objid = pg_get_serial_sequence('asset_relationships', 'id')::regclass "
                "AND dependency.refobjid = 'asset_relationships'::regclass "
                "AND dependency.deptype IN ('a', 'i'))"
            )
            assert cursor.fetchone()[0] is True

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _SEQUENCE_RUNTIME_LOGIN),
            future=True,
        )
        with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
            verify_runtime_database_authority(runtime_engine)
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        if original_owner is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("ALTER TABLE asset_relationships OWNER TO {}").format(sql.Identifier(original_owner))
                )
        _drop_roles(database_url, _SEQUENCE_RUNTIME_LOGIN, _SEQUENCE_OWNER_ROLE)
        operator_engine.dispose()
