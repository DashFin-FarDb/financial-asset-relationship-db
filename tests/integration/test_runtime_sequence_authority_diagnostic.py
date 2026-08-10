"""Focused PostgreSQL diagnostics for runtime sequence authority verification."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import sql  # noqa: E402  # type: ignore[import-untyped]

from src.data import database as database_module  # noqa: E402

pytestmark = pytest.mark.integration

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_RUNTIME_LOGIN = "cq1608_sequence_diagnostic"


def _database_url() -> str:
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        pytest.skip("disposable PostgreSQL authority tests are not enabled")
    database_url = os.getenv(_EPHEMERAL_POSTGRES_URL)
    if not database_url:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} is required")
    return database_url


def _runtime_connection(database_url: str):
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(_RUNTIME_LOGIN)))
    connection.autocommit = False
    return connection


def test_sequence_authority_helpers_execute_against_postgresql() -> None:
    """Expose raw catalog failures before the production verifier sanitizes them."""
    database_url = _database_url()
    operator_engine = None
    runtime_engine = None
    sequence_name: str | None = None

    try:
        operator_engine = create_engine(database_url, future=True)
        database_module.init_db(operator_engine)
        database_module.ensure_runtime_database_capabilities(
            operator_engine,
            {database_module.GRAPH_RUNTIME_CAPABILITY},
        )

        connection = psycopg2.connect(database_url)
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
                    ).format(sql.Identifier(_RUNTIME_LOGIN))
                )
                cursor.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(database_module.GRAPH_RUNTIME_ROLE),
                        sql.Identifier(_RUNTIME_LOGIN),
                    )
                )
                cursor.execute("SELECT pg_get_serial_sequence('asset_relationships', 'id')")
                sequence_name = cursor.fetchone()[0]
                assert isinstance(sequence_name, str) and sequence_name
                cursor.execute(
                    sql.SQL("GRANT UPDATE ON SEQUENCE {} TO {}").format(
                        sql.Identifier(*sequence_name.split(".")),
                        sql.Identifier(_RUNTIME_LOGIN),
                    )
                )
        finally:
            connection.close()

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url),
            future=True,
        )
        with runtime_engine.connect() as runtime_connection:
            database_module._verify_runtime_capability_catalog(  # pylint: disable=protected-access
                runtime_connection,
                (database_module.GRAPH_RUNTIME_CAPABILITY,),
            )
            with pytest.raises(
                database_module.SchemaCompatibilityError,
                match="runtime login sequence grants are incompatible",
            ):
                database_module._verify_runtime_login_sequence_grants(  # pylint: disable=protected-access
                    runtime_connection,
                    (database_module.GRAPH_RUNTIME_CAPABILITY,),
                )
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()

        connection = psycopg2.connect(database_url)
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                if sequence_name is not None:
                    cursor.execute(
                        sql.SQL("REVOKE UPDATE ON SEQUENCE {} FROM {}").format(
                            sql.Identifier(*sequence_name.split(".")),
                            sql.Identifier(_RUNTIME_LOGIN),
                        )
                    )
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(_RUNTIME_LOGIN)))
        finally:
            connection.close()

        if operator_engine is not None:
            operator_engine.dispose()
