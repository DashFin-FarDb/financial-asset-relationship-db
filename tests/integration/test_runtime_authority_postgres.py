"""Ephemeral-PostgreSQL regressions for runtime authority verification.

These tests create temporary roles and alter object ownership. They must run only
against the dedicated disposable PostgreSQL service in CI, never against staging
or another provider database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import sql  # noqa: E402  # type: ignore[import-untyped]
from sqlalchemy import create_engine  # noqa: E402

from src.data.database import (  # noqa: E402
    GRAPH_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_ROLE,
    SchemaCompatibilityError,
    _verify_runtime_capability_catalog,
    ensure_runtime_database_capabilities,
    init_db,
    verify_runtime_database_authority,
)

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_AUTH_RUNTIME_LOGIN = "cq1608_auth_runtime"
_AUTH_WRITE_ROLE = "cq1608_auth_writer"
_AUTH_REPLICATION_ROLE = "cq1608_auth_replication"
_AUTH_ORDINARY_ROLE = "cq1608_auth_ordinary"
_AUTH_INERT_CREATOR_LOGIN = "cq1608_auth_inert_creator"
_GRAPH_REPLICATION_ROLE = "cq1608_graph_replication"
_GRAPH_OTHER_CAPABILITY_LOGIN = "cq1608_graph_other_capability"
_GRAPH_NO_CAP_RUNTIME_LOGIN = "cq1608_graph_no_cap_runtime"
_GRAPH_NO_CAP_DIRECT_LOGIN = "cq1608_graph_no_cap_direct"
_GRAPH_ORDINARY_ROLE = "cq1608_graph_ordinary"
_GRAPH_EXTRA_RUNTIME_LOGIN = "cq1608_graph_extra_runtime"
_GRAPH_EXTRA_TRUNCATE_ROLE = "cq1608_graph_extra_truncate"
_GRAPH_DIRECT_SEQUENCE_LOGIN = "cq1608_graph_direct_sequence"
_SEQUENCE_RUNTIME_LOGIN = "cq1608_sequence_runtime"
_SEQUENCE_OWNER_ROLE = "cq1608_sequence_owner"
_RUNTIME_LOGIN_DDL = sql.SQL(
    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
)


def _ephemeral_database_url() -> str:
    """Return the disposable PostgreSQL URL or skip when the opt-in guard is absent."""
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        pytest.skip(f"Set {_EPHEMERAL_AUTHORITY_FLAG}=1 only for disposable PostgreSQL authority tests")
    database_url = os.getenv(_EPHEMERAL_POSTGRES_URL)
    if not database_url:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} is required when {_EPHEMERAL_AUTHORITY_FLAG}=1")
    assert database_url is not None
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} must be a PostgreSQL URL")
    return database_url


@contextmanager
def _operator_connection(database_url: str) -> Iterator[Any]:
    """Yield an autocommit operator connection for authority-fixture setup and cleanup."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        yield connection
    finally:
        connection.close()


def _runtime_connection(database_url: str, role_name: str):
    """Return a connection whose session authorization is the requested runtime role."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role_name)))
    connection.autocommit = False
    return connection


def _drop_roles(database_url: str, *role_names: str) -> None:
    """Drop disposable authority-test roles after their object grants have been removed."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for role_name in role_names:
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


def _prepare_auth_schema(database_url: str) -> None:
    """Create the auth schema against the explicit disposable operator target."""
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
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            if attack_role == "replication":
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS REPLICATION"
                    ).format(sql.Identifier(elevated_role))
                )
            else:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
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
        if attack_role == "credential_update":
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE UPDATE (hashed_password) ON TABLE user_credentials FROM {}").format(
                        sql.Identifier(_AUTH_WRITE_ROLE)
                    )
                )
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, elevated_role)


@pytest.mark.integration
def test_auth_runtime_rejects_unexpected_assumable_ordinary_role() -> None:
    """The auth login may assume only fardb_runtime_auth."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.ensure_runtime_access()

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))

            ordinary_role_ddl = sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(ordinary_role_ddl.format(sql.Identifier(_AUTH_ORDINARY_ROLE)))

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_AUTH_ORDINARY_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="capability memberships are incompatible"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, _AUTH_ORDINARY_ROLE)


@pytest.mark.integration
def test_auth_runtime_rejects_inert_creator_admin_option() -> None:
    """An inert creator with ADMIN OPTION can re-delegate the auth capability."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.ensure_runtime_access()

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_AUTH_INERT_CREATOR_LOGIN)))
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION, INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_INERT_CREATOR_LOGIN),
                )
            )

        with (
            api_database.bind_database_url(database_url),
            pytest.raises(psycopg2.Error, match="unsafe FarDB capability role"),
        ):
            api_database.ensure_runtime_access()

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, _AUTH_INERT_CREATOR_LOGIN)


@pytest.mark.integration
@pytest.mark.parametrize("membership_posture", ["delegable", "usable"])
def test_runtime_database_authority_rejects_unsafe_capability_grantee(membership_posture: str) -> None:
    """No other login may delegate or use an application capability."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    runtime_engine = None

    try:
        init_db(operator_engine)
        ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN)))
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_GRAPH_OTHER_CAPABILITY_LOGIN)))
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN),
                )
            )
            membership_options = (
                sql.SQL("WITH ADMIN OPTION, INHERIT FALSE, SET FALSE")
                if membership_posture == "delegable"
                else sql.SQL("WITH INHERIT TRUE, SET TRUE")
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_OTHER_CAPABILITY_LOGIN),
                    membership_options,
                )
            )

        with (
            operator_engine.connect() as connection,
            pytest.raises(
                SchemaCompatibilityError,
                match="unsafe or missing runtime capability role",
            ),
        ):
            _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _GRAPH_EXTRA_RUNTIME_LOGIN),
            future=True,
        )
        with pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"):
            verify_runtime_database_authority(
                runtime_engine,
                required_capabilities={GRAPH_RUNTIME_CAPABILITY},
            )
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        _drop_roles(database_url, _GRAPH_EXTRA_RUNTIME_LOGIN, _GRAPH_OTHER_CAPABILITY_LOGIN)
        operator_engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("assumable_role", "role_attribute", "expected_error"),
    [
        (_GRAPH_ORDINARY_ROLE, "NOREPLICATION", "capability memberships are incompatible"),
        (_GRAPH_REPLICATION_ROLE, "REPLICATION", "retains schema-migration authority"),
    ],
)
def test_runtime_database_authority_rejects_unexpected_assumable_role_without_capabilities(
    assumable_role: str,
    role_attribute: str,
    expected_error: str,
) -> None:
    """A no-capability runtime login may not retain any assumable role membership."""
    database_url = _ephemeral_database_url()
    runtime_engine = None
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_NO_CAP_RUNTIME_LOGIN)))

            assumable_role_ddl = sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS {}"
            ).format(
                sql.Identifier(assumable_role),
                sql.SQL(role_attribute),
            )
            cursor.execute(assumable_role_ddl)

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(assumable_role),
                    sql.Identifier(_GRAPH_NO_CAP_RUNTIME_LOGIN),
                )
            )

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _GRAPH_NO_CAP_RUNTIME_LOGIN),
            future=True,
        )
        with pytest.raises(SchemaCompatibilityError, match=expected_error):
            verify_runtime_database_authority(runtime_engine)
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        _drop_roles(database_url, _GRAPH_NO_CAP_RUNTIME_LOGIN, assumable_role)


@pytest.mark.integration
def test_runtime_database_authority_enforces_zero_managed_privileges_without_capabilities() -> None:
    """A no-capability login may hold no managed table, column, or sequence privilege."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    runtime_engine = None
    sequence_name: str | None = None

    try:
        init_db(operator_engine)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN)))
            cursor.execute("SELECT pg_get_serial_sequence('asset_relationships', 'id')")
            sequence_name = cursor.fetchone()[0]
            assert isinstance(sequence_name, str) and sequence_name

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _GRAPH_NO_CAP_DIRECT_LOGIN),
            future=True,
        )

        verify_runtime_database_authority(runtime_engine)

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT INSERT ON TABLE assets TO {}").format(sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN))
            )
        with pytest.raises(SchemaCompatibilityError, match="runtime login grants are incompatible on assets"):
            verify_runtime_database_authority(runtime_engine)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE INSERT ON TABLE assets FROM {}").format(sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN))
            )
            cursor.execute(
                sql.SQL("GRANT UPDATE (price) ON TABLE assets TO {}").format(sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN))
            )
        with pytest.raises(SchemaCompatibilityError, match="runtime login column grants are incompatible on assets"):
            verify_runtime_database_authority(runtime_engine)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE UPDATE (price) ON TABLE assets FROM {}").format(
                    sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN)
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(*sequence_name.split(".")),
                    sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN),
                )
            )
        with pytest.raises(SchemaCompatibilityError, match="runtime login sequence grants are incompatible"):
            verify_runtime_database_authority(runtime_engine)
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        if sequence_name is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON TABLE assets FROM {}").format(
                        sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE UPDATE (price) ON TABLE assets FROM {}").format(
                        sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM {}").format(
                        sql.Identifier(*sequence_name.split(".")),
                        sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN),
                    )
                )
        _drop_roles(database_url, _GRAPH_NO_CAP_DIRECT_LOGIN)
        operator_engine.dispose()


@pytest.mark.integration
def test_runtime_database_authority_rejects_unexpected_assumable_truncate_role() -> None:
    """Unexpected role membership cannot retain whole-table write authority."""
    database_url = _ephemeral_database_url()
    operator_engine = None
    runtime_engine = None
    extra_role_created = False

    try:
        operator_engine = create_engine(database_url, future=True)
        init_db(operator_engine)
        ensure_runtime_database_capabilities(
            operator_engine,
            {GRAPH_RUNTIME_CAPABILITY},
        )

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN)))

            extra_role_ddl = sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(extra_role_ddl.format(sql.Identifier(_GRAPH_EXTRA_TRUNCATE_ROLE)))
            extra_role_created = True

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT TRUNCATE ON TABLE assets TO {}").format(sql.Identifier(_GRAPH_EXTRA_TRUNCATE_ROLE))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_GRAPH_EXTRA_TRUNCATE_ROLE),
                    sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN),
                )
            )

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _GRAPH_EXTRA_RUNTIME_LOGIN,
            ),
            future=True,
        )

        with pytest.raises(
            SchemaCompatibilityError,
            match="capability memberships are incompatible",
        ):
            verify_runtime_database_authority(
                runtime_engine,
                required_capabilities={GRAPH_RUNTIME_CAPABILITY},
            )
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()

        if extra_role_created:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE TRUNCATE ON TABLE assets FROM {}").format(
                        sql.Identifier(_GRAPH_EXTRA_TRUNCATE_ROLE)
                    )
                )

        _drop_roles(
            database_url,
            _GRAPH_EXTRA_RUNTIME_LOGIN,
            _GRAPH_EXTRA_TRUNCATE_ROLE,
        )
        if operator_engine is not None:
            operator_engine.dispose()


@pytest.mark.integration
def test_runtime_database_authority_rejects_direct_sequence_update_grant() -> None:
    """Direct sequence UPDATE may not exceed the graph capability contract."""
    database_url = _ephemeral_database_url()
    operator_engine = None
    runtime_engine = None
    sequence_name: str | None = None

    try:
        operator_engine = create_engine(database_url, future=True)
        init_db(operator_engine)
        ensure_runtime_database_capabilities(
            operator_engine,
            {GRAPH_RUNTIME_CAPABILITY},
        )

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_GRAPH_DIRECT_SEQUENCE_LOGIN)))

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_DIRECT_SEQUENCE_LOGIN),
                )
            )

            cursor.execute("SELECT pg_get_serial_sequence('asset_relationships', 'id')")
            sequence_name = cursor.fetchone()[0]
            assert isinstance(sequence_name, str) and sequence_name

            cursor.execute(
                sql.SQL("GRANT UPDATE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(*sequence_name.split(".")),
                    sql.Identifier(_GRAPH_DIRECT_SEQUENCE_LOGIN),
                )
            )

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _GRAPH_DIRECT_SEQUENCE_LOGIN,
            ),
            future=True,
        )

        with pytest.raises(
            SchemaCompatibilityError,
            match="runtime login sequence grants are incompatible",
        ):
            verify_runtime_database_authority(
                runtime_engine,
                required_capabilities={GRAPH_RUNTIME_CAPABILITY},
            )
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()

        if sequence_name is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE UPDATE ON SEQUENCE {} FROM {}").format(
                        sql.Identifier(*sequence_name.split(".")),
                        sql.Identifier(_GRAPH_DIRECT_SEQUENCE_LOGIN),
                    )
                )

        _drop_roles(
            database_url,
            _GRAPH_DIRECT_SEQUENCE_LOGIN,
        )
        if operator_engine is not None:
            operator_engine.dispose()


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
                sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION").format(
                    sql.Identifier(_SEQUENCE_OWNER_ROLE)
                )
            )
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_SEQUENCE_RUNTIME_LOGIN)))
            cursor.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE)))
            cursor.execute(
                sql.SQL("ALTER TABLE asset_relationships OWNER TO {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE))
            )
            cursor.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(_SEQUENCE_OWNER_ROLE))
            )
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
