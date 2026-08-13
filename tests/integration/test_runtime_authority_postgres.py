"""Ephemeral-PostgreSQL regressions for runtime authority verification.

These tests create temporary roles and alter object ownership. They must run only
against the dedicated disposable PostgreSQL service in CI, never against staging
or another provider database.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import sql  # noqa: E402  # type: ignore[import-untyped]
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from src.data.database import (  # noqa: E402
    COORDINATION_RUNTIME_CAPABILITY,
    COORDINATION_RUNTIME_ROLE,
    GRAPH_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_ROLE,
    RUNTIME_CAPABILITY_ROLES,
    CapabilityRoleBootstrapRequiredError,
    SchemaCompatibilityError,
    _verify_runtime_capability_catalog,
    ensure_runtime_database_capabilities,
    init_db,
    verify_runtime_database_authority,
)

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_CAPABILITY_BOOTSTRAP_SQL = Path(__file__).parents[2] / "scripts" / "bootstrap_database_capability_roles.sql"
_AUTH_RUNTIME_LOGIN = "cq1608_auth_runtime"
_AUTH_WRITE_ROLE = "cq1608_auth_writer"
_AUTH_REPLICATION_ROLE = "cq1608_auth_replication"
_AUTH_ORDINARY_ROLE = "cq1608_auth_ordinary"
_AUTH_INERT_CREATOR_LOGIN = "cq1608_auth_inert_creator"
_AUTH_MEMBERSHIP_BRIDGE_ROLE = "cq1608_auth_membership_bridge"
_AUTH_USABLE_PATH_ROLE = "cq1608_auth_usable_path"
_AUTH_UNRELATED_SCHEMA = "cq1608_auth_unrelated_schema"
_GRAPH_REPLICATION_ROLE = "cq1608_graph_replication"
_GRAPH_OTHER_CAPABILITY_LOGIN = "cq1608_graph_other_capability"
_GRAPH_SUPERUSER_ROLE = "cq1608_graph_superuser"
_BOOTSTRAP_MIGRATION_OWNER = "cq1608_bootstrap_migration_owner"
_BOOTSTRAP_SCHEMA = "cq1608_bootstrap_schema"
_BOOTSTRAP_UNRELATED_SCHEMA = "cq1608_bootstrap_unrelated_schema"
_BOOTSTRAP_GRAPH_RUNTIME_LOGIN = "cq1608_bootstrap_graph_runtime"
_BOOTSTRAP_AUTH_RUNTIME_LOGIN = "cq1608_bootstrap_auth_runtime"
_MISSING_ROLE_MIGRATION_OWNER = "cq1608_missing_role_owner"
_MISSING_ROLE_SCHEMA = "cq1608_missing_role_schema"
_MISSING_GRAPH_ROLE = "cq1608_missing_graph_capability"
_MISSING_COORDINATION_ROLE = "cq1608_missing_coordination_capability"
_GRAPH_NO_CAP_RUNTIME_LOGIN = "cq1608_graph_no_cap_runtime"
_GRAPH_NO_CAP_DIRECT_LOGIN = "cq1608_graph_no_cap_direct"
_GRAPH_ORDINARY_ROLE = "cq1608_graph_ordinary"
_GRAPH_EXTRA_RUNTIME_LOGIN = "cq1608_graph_extra_runtime"
_GRAPH_EXTRA_TRUNCATE_ROLE = "cq1608_graph_extra_truncate"
_GRAPH_DIRECT_SEQUENCE_LOGIN = "cq1608_graph_direct_sequence"
_GRAPH_UNRELATED_SCHEMA = "cq1608_graph_unrelated_schema"
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


def _runtime_connection(database_url: str, role_name: str, schema_name: str | None = None):
    """Return a connection whose session authorization is the requested runtime role."""
    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role_name)))
        if schema_name is not None:
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
    connection.autocommit = False
    return connection


def _drop_roles(database_url: str, *role_names: str) -> None:
    """Drop disposable authority-test roles after their object grants have been removed."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for role_name in role_names:
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


def _drop_schema(database_url: str, schema_name: str) -> None:
    """Drop one disposable authority-test schema and all objects it owns."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))


def _move_capability_roles_aside(database_url: str) -> tuple[dict[str, str], set[str]]:
    """Temporarily rename existing disposable-cluster capability roles for bootstrap coverage."""
    import api.database as api_database

    role_backups = {
        api_database.AUTH_RUNTIME_ROLE: "cq1608_saved_runtime_auth",
        GRAPH_RUNTIME_ROLE: "cq1608_saved_runtime_graph",
        COORDINATION_RUNTIME_ROLE: "cq1608_saved_runtime_coordination",
    }
    moved: set[str] = set()
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for original, backup in role_backups.items():
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (backup,))
            if cursor.fetchone()[0]:
                pytest.fail(f"disposable PostgreSQL contains stale bootstrap backup role {backup}")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (original,))
            if cursor.fetchone()[0]:
                cursor.execute(
                    sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                        sql.Identifier(original),
                        sql.Identifier(backup),
                    )
                )
                moved.add(original)
    return role_backups, moved


def _restore_capability_roles(
    database_url: str,
    role_backups: dict[str, str],
    moved: set[str],
) -> None:
    """Drop test-created canonical roles and restore any roles moved aside."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for original in role_backups:
            if original not in moved:
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(original)))
        for original, backup in role_backups.items():
            if original in moved:
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(original)))
                cursor.execute(
                    sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                        sql.Identifier(backup),
                        sql.Identifier(original),
                    )
                )


def _prepare_auth_schema(database_url: str) -> None:
    """Create the auth schema against the explicit disposable operator target."""
    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.initialize_schema()


@pytest.mark.integration
def test_api_postgres_statement_timeout_is_driver_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled auth query must be interrupted by the PostgreSQL driver setting."""
    database_url = _ephemeral_database_url()
    import api.database as api_database

    monkeypatch.setattr(api_database, "_POSTGRES_STATEMENT_TIMEOUT_MILLISECONDS", 50)
    started = time.monotonic()
    with (
        api_database.bind_database_url(database_url),
        api_database._bind_postgres_operation_guard(api_database._PostgresOperationGuard()),
        pytest.raises(psycopg2.errors.QueryCanceled),
    ):
        api_database.fetch_value("SELECT pg_sleep(1)")
    assert time.monotonic() - started < 1


@pytest.mark.integration
def test_auth_runtime_uses_only_inherited_or_settable_membership_paths() -> None:
    """PostgreSQL 16 inert, direct, and transitive memberships retain exact authority."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)
    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.ensure_runtime_access()

    def _verify_runtime(error: str | None = None) -> None:
        """Verify the disposable auth login with an optional expected failure."""
        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
        ):
            if error is None:
                api_database.verify_runtime_authority()
                return
            with pytest.raises(SchemaCompatibilityError, match=error):
                api_database.verify_runtime_authority()

    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        if int(cursor.fetchone()[0]) < 160000:
            pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            role_ddl = sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION")
            cursor.execute(role_ddl.format(sql.Identifier(_AUTH_USABLE_PATH_ROLE)))
            cursor.execute(role_ddl.format(sql.Identifier(_AUTH_MEMBERSHIP_BRIDGE_ROLE)))
            cursor.execute(
                sql.SQL("GRANT UPDATE (hashed_password) ON TABLE user_credentials TO {}").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE)
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )

            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime()

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET FALSE").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_AUTH_MEMBERSHIP_BRIDGE_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE),
                    sql.Identifier(_AUTH_MEMBERSHIP_BRIDGE_ROLE),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(_AUTH_MEMBERSHIP_BRIDGE_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime()
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE UPDATE (hashed_password) ON TABLE user_credentials FROM {}").format(
                    sql.Identifier(_AUTH_USABLE_PATH_ROLE)
                )
            )
        _drop_roles(
            database_url,
            _AUTH_RUNTIME_LOGIN,
            _AUTH_MEMBERSHIP_BRIDGE_ROLE,
            _AUTH_USABLE_PATH_ROLE,
        )


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
def test_auth_runtime_rejects_capability_create_on_non_current_schema() -> None:
    """Auth provisioning and startup reject capability CREATE on any schema."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)
    import api.database as api_database

    with api_database.bind_database_url(database_url):
        api_database.ensure_runtime_access()

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(_AUTH_UNRELATED_SCHEMA))
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_AUTH_UNRELATED_SCHEMA),
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
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
            pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_schema(database_url, _AUTH_UNRELATED_SCHEMA)
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN)


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
def test_non_superuser_migration_owner_cannot_create_missing_capability_role() -> None:
    """A CREATEROLE migration owner must stop before creating a missing capability role."""
    database_url = _ephemeral_database_url()
    migration_engine = None
    capability_roles = {
        GRAPH_RUNTIME_CAPABILITY: _MISSING_GRAPH_ROLE,
        COORDINATION_RUNTIME_CAPABILITY: _MISSING_COORDINATION_ROLE,
    }

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("PostgreSQL 16 capability-role bootstrap regression")
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB CREATEROLE " "NOBYPASSRLS NOREPLICATION").format(
                    sql.Identifier(_MISSING_ROLE_MIGRATION_OWNER)
                )
            )
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(_MISSING_ROLE_SCHEMA),
                    sql.Identifier(_MISSING_ROLE_MIGRATION_OWNER),
                )
            )

        migration_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _MISSING_ROLE_MIGRATION_OWNER,
                _MISSING_ROLE_SCHEMA,
            ),
            future=True,
        )
        init_db(migration_engine)
        with (
            patch.dict(RUNTIME_CAPABILITY_ROLES, capability_roles, clear=True),
            pytest.raises(
                CapabilityRoleBootstrapRequiredError,
                match="bootstrap_database_capability_roles.sql as a PostgreSQL superuser",
            ),
        ):
            ensure_runtime_database_capabilities(migration_engine, {GRAPH_RUNTIME_CAPABILITY})

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM pg_roles WHERE rolname = ANY(%s)",
                (list(capability_roles.values()),),
            )
            assert cursor.fetchone()[0] == 0
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        _drop_schema(database_url, _MISSING_ROLE_SCHEMA)
        _drop_roles(
            database_url,
            _MISSING_GRAPH_ROLE,
            _MISSING_COORDINATION_ROLE,
            _MISSING_ROLE_MIGRATION_OWNER,
        )


@pytest.mark.integration
def test_superuser_bootstrap_enables_least_privilege_migration_and_runtime_verification() -> None:
    """Bootstrap creates safe roles consumed by migration and restricted runtimes."""
    database_url = _ephemeral_database_url()
    migration_engine = None
    graph_runtime_engine = None
    role_backups: dict[str, str] = {}
    moved_roles: set[str] = set()

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("PostgreSQL 16 capability-role bootstrap regression")

        role_backups, moved_roles = _move_capability_roles_aside(database_url)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB CREATEROLE " "NOBYPASSRLS NOREPLICATION").format(
                    sql.Identifier(_BOOTSTRAP_MIGRATION_OWNER)
                )
            )

        creator_connection = _runtime_connection(database_url, _BOOTSTRAP_MIGRATION_OWNER)
        try:
            with creator_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
                    ).format(sql.Identifier(GRAPH_RUNTIME_ROLE))
                )
            creator_connection.commit()
        finally:
            creator_connection.close()

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM pg_auth_members AS membership "
                "JOIN pg_roles AS role ON role.oid = membership.roleid "
                "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                "WHERE role.rolname = %s AND grantee.rolname = %s AND membership.admin_option",
                (GRAPH_RUNTIME_ROLE, _BOOTSTRAP_MIGRATION_OWNER),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(_CAPABILITY_BOOTSTRAP_SQL.read_text(encoding="utf-8"))
            cursor.execute(
                "SELECT COUNT(*) FROM pg_roles WHERE rolname = ANY(%s) "
                "AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb "
                "AND NOT rolcreaterole AND NOT rolbypassrls AND NOT rolreplication",
                (list(role_backups),),
            )
            assert cursor.fetchone()[0] == 3
            cursor.execute(
                "SELECT COUNT(*) FROM pg_auth_members AS membership "
                "JOIN pg_roles AS role ON role.oid = membership.roleid "
                "WHERE role.rolname = ANY(%s) AND membership.admin_option",
                (list(role_backups),),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT COUNT(*) FROM pg_auth_members AS membership "
                "JOIN pg_roles AS role ON role.oid = membership.roleid "
                "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                "WHERE role.rolname = %s AND grantee.rolname = %s",
                (GRAPH_RUNTIME_ROLE, _BOOTSTRAP_MIGRATION_OWNER),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                    sql.Identifier(_BOOTSTRAP_SCHEMA),
                    sql.Identifier(_BOOTSTRAP_MIGRATION_OWNER),
                )
            )

        migration_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _BOOTSTRAP_MIGRATION_OWNER,
                _BOOTSTRAP_SCHEMA,
            ),
            future=True,
        )
        init_db(migration_engine)
        capabilities = {GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY}
        ensure_runtime_database_capabilities(migration_engine, capabilities)

        import api.database as api_database

        with (
            api_database.bind_database_url(database_url),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(
                    database_url,
                    _BOOTSTRAP_MIGRATION_OWNER,
                    _BOOTSTRAP_SCHEMA,
                ),
            ),
        ):
            api_database.initialize_schema()
            api_database.ensure_runtime_access()
            api_database.verify_schema_compatibility()

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_BOOTSTRAP_GRAPH_RUNTIME_LOGIN)))
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_BOOTSTRAP_AUTH_RUNTIME_LOGIN)))
            for role_name in (GRAPH_RUNTIME_ROLE, COORDINATION_RUNTIME_ROLE):
                cursor.execute(
                    sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                        sql.Identifier(role_name),
                        sql.Identifier(_BOOTSTRAP_GRAPH_RUNTIME_LOGIN),
                    )
                )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_BOOTSTRAP_AUTH_RUNTIME_LOGIN),
                )
            )

        graph_runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _BOOTSTRAP_GRAPH_RUNTIME_LOGIN,
                _BOOTSTRAP_SCHEMA,
            ),
            future=True,
        )
        verify_runtime_database_authority(
            graph_runtime_engine,
            required_capabilities=capabilities,
        )
        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda: _runtime_connection(
                    database_url,
                    _BOOTSTRAP_AUTH_RUNTIME_LOGIN,
                    _BOOTSTRAP_SCHEMA,
                ),
            ),
        ):
            api_database.verify_runtime_authority()
    finally:
        if graph_runtime_engine is not None:
            graph_runtime_engine.dispose()
        if migration_engine is not None:
            migration_engine.dispose()
        _drop_schema(database_url, _BOOTSTRAP_SCHEMA)
        _drop_roles(
            database_url,
            _BOOTSTRAP_GRAPH_RUNTIME_LOGIN,
            _BOOTSTRAP_AUTH_RUNTIME_LOGIN,
            _BOOTSTRAP_MIGRATION_OWNER,
        )
        if role_backups:
            _restore_capability_roles(database_url, role_backups, moved_roles)


@pytest.mark.integration
def test_capability_bootstrap_rejects_create_on_non_current_schema() -> None:
    """A capability role may not retain CREATE on any schema in the database."""
    database_url = _ephemeral_database_url()
    bootstrap_sql = _CAPABILITY_BOOTSTRAP_SQL.read_text(encoding="utf-8")

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(bootstrap_sql)
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                    sql.Identifier(_BOOTSTRAP_UNRELATED_SCHEMA)
                )
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_BOOTSTRAP_UNRELATED_SCHEMA),
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                )
            )
            cursor.execute("SELECT current_schema()")
            assert cursor.fetchone()[0] != _BOOTSTRAP_UNRELATED_SCHEMA

            with pytest.raises(psycopg2.Error, match="unsafe FarDB capability role"):
                cursor.execute(bootstrap_sql)
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(_BOOTSTRAP_UNRELATED_SCHEMA))
            )


@pytest.mark.integration
def test_graph_runtime_rejects_capability_create_on_non_current_schema() -> None:
    """Graph provisioning, catalog, and startup reject CREATE on any schema."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    runtime_engine = None

    try:
        init_db(operator_engine)
        ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN)))
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(_GRAPH_UNRELATED_SCHEMA))
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_GRAPH_UNRELATED_SCHEMA),
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                )
            )

        with pytest.raises(DBAPIError, match="unsafe FarDB capability role"):
            ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

        with (
            operator_engine.connect() as connection,
            pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"),
        ):
            _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _GRAPH_EXTRA_RUNTIME_LOGIN),
            future=True,
        )
        with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
            verify_runtime_database_authority(
                runtime_engine,
                required_capabilities={GRAPH_RUNTIME_CAPABILITY},
            )
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        _drop_schema(database_url, _GRAPH_UNRELATED_SCHEMA)
        _drop_roles(database_url, _GRAPH_EXTRA_RUNTIME_LOGIN)
        operator_engine.dispose()


@pytest.mark.integration
def test_runtime_database_authority_rejects_capability_reachable_through_superuser_role() -> None:
    """A login may not reach a capability through an intermediate superuser role."""
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
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN)))
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_OTHER_CAPABILITY_LOGIN)))
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN INHERIT SUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(_GRAPH_SUPERUSER_ROLE))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_EXTRA_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(_GRAPH_SUPERUSER_ROLE),
                    sql.Identifier(_GRAPH_OTHER_CAPABILITY_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_GRAPH_SUPERUSER_ROLE),
                )
            )

        with pytest.raises(DBAPIError, match="unsafe FarDB capability role"):
            ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

        with (
            operator_engine.connect() as connection,
            pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"),
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
        _drop_roles(
            database_url,
            _GRAPH_EXTRA_RUNTIME_LOGIN,
            _GRAPH_OTHER_CAPABILITY_LOGIN,
            _GRAPH_SUPERUSER_ROLE,
        )
        operator_engine.dispose()


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

        with pytest.raises(DBAPIError, match="unsafe FarDB capability role"):
            ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

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
def test_capability_catalog_verification_has_bounded_round_trips() -> None:
    """The full two-capability grant matrix must remain set-based."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    statement_count = 0

    def _count_statement(*_args, **_kwargs) -> None:
        """Count driver executions inside the focused catalog verification window."""
        nonlocal statement_count
        statement_count += 1

    try:
        init_db(operator_engine)
        capabilities = {GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY}
        ensure_runtime_database_capabilities(operator_engine, capabilities)
        event.listen(operator_engine, "before_cursor_execute", _count_statement)
        with operator_engine.connect() as connection:
            _verify_runtime_capability_catalog(
                connection,
                (GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY),
            )
        assert statement_count <= 9
    finally:
        if event.contains(operator_engine, "before_cursor_execute", _count_statement):
            event.remove(operator_engine, "before_cursor_execute", _count_statement)
        operator_engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("owned_table", "has_application_sequence"),
    [("assets", False), ("asset_relationships", True)],
)
def test_capability_catalog_rejects_managed_relation_ownership(
    owned_table: str,
    has_application_sequence: bool,
) -> None:
    """Migration verification rejects capability-owned tables and linked sequences."""
    database_url = _ephemeral_database_url()
    operator_engine = create_engine(database_url, future=True)
    original_owner: str | None = None

    try:
        init_db(operator_engine)
        ensure_runtime_database_capabilities(operator_engine, {GRAPH_RUNTIME_CAPABILITY})

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = {}::regclass").format(
                    sql.Literal(owned_table)
                )
            )
            original_owner = cursor.fetchone()[0]
            assert isinstance(original_owner, str)
            assert original_owner
            cursor.execute(
                sql.SQL("ALTER TABLE {} OWNER TO {}").format(
                    sql.Identifier(owned_table),
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                )
            )
            if has_application_sequence:
                cursor.execute(
                    sql.SQL(
                        "SELECT pg_get_userbyid(relowner) FROM pg_class "
                        "WHERE oid = pg_get_serial_sequence({}, 'id')::regclass"
                    ).format(sql.Literal(owned_table))
                )
                assert cursor.fetchone()[0] == GRAPH_RUNTIME_ROLE

        with (
            operator_engine.connect() as connection,
            pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"),
        ):
            _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))
    finally:
        if original_owner is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("ALTER TABLE {} OWNER TO {}").format(
                        sql.Identifier(owned_table),
                        sql.Identifier(original_owner),
                    )
                )
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
        ensure_runtime_database_capabilities(operator_engine, {COORDINATION_RUNTIME_CAPABILITY})
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_GRAPH_NO_CAP_DIRECT_LOGIN)))
            cursor.execute("SELECT pg_get_serial_sequence('asset_relationships', 'id')")
            sequence_name = cursor.fetchone()[0]
            assert isinstance(sequence_name, str)
            assert sequence_name

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
            assert isinstance(sequence_name, str)
            assert sequence_name

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
            assert isinstance(original_owner, str)
            assert original_owner

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
