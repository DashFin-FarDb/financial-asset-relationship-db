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
from dataclasses import replace
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest

from tests.integration.postgresql_disposable_cluster import (
    ContainerCliRunner,
    DisposableTargetError,
    OwnedRoleCursor,
    allocate_role_names,
    attested_connection,
    connect_attested,
    connect_owned_attested,
    create_attested_engine,
    execute_capability_bootstrap,
    invocation_id,
    owned_role_oid,
    record_created_role,
    role_name_candidate,
    verify_applied_profile,
)

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import sql  # noqa: E402  # type: ignore[import-untyped]
from sqlalchemy import create_engine, event  # noqa: E402

from src.data.database import (  # noqa: E402
    COORDINATION_RUNTIME_CAPABILITY,
    COORDINATION_RUNTIME_ROLE,
    GRAPH_RUNTIME_CAPABILITY,
    GRAPH_RUNTIME_ROLE,
    SchemaCompatibilityError,
    _verify_runtime_capability_catalog,
    verify_runtime_database_authority,
)

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_ISOLATED_DATABASE_ADMIN_URLS: dict[str, str] = {}
_DEFERRED_CAPABILITY_ROLE_RESTORATIONS: dict[str, tuple[dict[str, str], set[str]]] = {}
_AUTH_RUNTIME_LOGIN = "fardb_login_auth"
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
_BOOTSTRAP_UNRELATED_SCHEMA = "cq1608_bootstrap_unrelated_schema"
_BOOTSTRAP_GRAPH_RUNTIME_LOGIN = "fardb_login_graph"
_BOOTSTRAP_AUTH_RUNTIME_LOGIN = "fardb_login_auth"
_MISSING_ROLE_MIGRATION_OWNER = "cq1608_missing_role_owner"
_GRAPH_NO_CAP_RUNTIME_LOGIN = "cq1608_graph_no_cap_runtime"
_GRAPH_NO_CAP_DIRECT_LOGIN = "cq1608_graph_no_cap_direct"
_GRAPH_ORDINARY_ROLE = "cq1608_graph_ordinary"
_GRAPH_EXTRA_RUNTIME_LOGIN = "cq1608_graph_extra_runtime"
_GRAPH_EXTRA_TRUNCATE_ROLE = "cq1608_graph_extra_truncate"
_GRAPH_DIRECT_SEQUENCE_LOGIN = "fardb_login_graph"
_GRAPH_UNRELATED_SCHEMA = "cq1608_graph_unrelated_schema"
_SEQUENCE_RUNTIME_LOGIN = "cq1608_sequence_runtime"
_SEQUENCE_OWNER_ROLE = "cq1608_sequence_owner"
_RUNTIME_LOGIN_DDL = sql.SQL(
    "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
)
_ORIGINAL_ROLE_NAMES = {
    name: value
    for name, value in tuple(globals().items())
    if name.isupper() and isinstance(value, str) and value.startswith("cq1608_")
}


class _RoleAllocation:
    """Publish names only after complete allocation on an attested invocation."""

    def __init__(self) -> None:
        """Create empty allocation state and its initialization lock."""
        import threading

        self.names: dict[str, str] = {}
        self.invocation: str | None = None
        self.lock = threading.Lock()

    def initialize(self, database_url: str) -> None:
        """Reject cross-invocation reuse and leave failed initialization unpublished."""
        invocation = invocation_id()
        with self.lock:
            if self.invocation is not None:
                if self.invocation != invocation:
                    raise DisposableTargetError("role allocation belongs to a different invocation")
                return
            with attested_connection(database_url) as connection:
                names = allocate_role_names(connection, _ORIGINAL_ROLE_NAMES)
            self.names = names
            self.invocation = invocation


_ROLE_ALLOCATION = _RoleAllocation()
_CAPABILITY_BACKUP_OIDS: dict[str, int] = {}


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
    _ROLE_ALLOCATION.initialize(database_url)
    from scripts.postgresql_ledger import PlannedTarget, assert_profile_write_allowed

    target = PlannedTarget(
        logical_targets=("graph",),
        profile="graph",
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=database_url,
    )
    assert_profile_write_allowed(target)
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "disable"
    database_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    assert_profile_write_allowed(replace(target, database_url=database_url))
    return database_url


@pytest.fixture(autouse=True)
def _isolated_profile_database(monkeypatch: pytest.MonkeyPatch):
    """Give each authority test a new disposable database for its exact ledger profile."""
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        yield
        return
    from scripts.postgresql_ledger import PlannedTarget, assert_profile_write_allowed

    base_url = os.environ.get(_EPHEMERAL_POSTGRES_URL)
    if not base_url:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} is required when {_EPHEMERAL_AUTHORITY_FLAG}=1")
    assert base_url is not None
    target = PlannedTarget(
        logical_targets=("graph",),
        profile="graph",
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=base_url,
    )
    assert_profile_write_allowed(target)
    parsed = urlsplit(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "disable"
    base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    assert_profile_write_allowed(replace(target, database_url=base_url))
    database_name = f"fardb_authority_{uuid4().hex}"
    parsed = urlsplit(base_url)
    isolated_url = urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))
    assert_profile_write_allowed(replace(target, database_url=isolated_url))
    with _operator_connection(base_url) as connection, connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    _ISOLATED_DATABASE_ADMIN_URLS[database_name] = base_url
    monkeypatch.setenv(_EPHEMERAL_POSTGRES_URL, isolated_url)
    try:
        yield
    finally:
        with _operator_connection(base_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))
        restoration = _DEFERRED_CAPABILITY_ROLE_RESTORATIONS.pop(database_name, None)
        if restoration is not None:
            role_backups, moved_roles = restoration
            _restore_capability_roles(base_url, role_backups, moved_roles)
        _ISOLATED_DATABASE_ADMIN_URLS.pop(database_name, None)


@contextmanager
def _operator_connection(database_url: str) -> Iterator[Any]:
    """Yield an autocommit operator connection for authority-fixture setup and cleanup."""
    connection = connect_owned_attested(database_url)
    connection.autocommit = True
    canonical_before: set[str]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
            (["fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination"],),
        )
        canonical_before = {row[0] for row in cursor.fetchall()}
    try:
        yield connection
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (["fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination"],),
            )
            for (name,) in cursor.fetchall():
                if name not in canonical_before:
                    record_created_role(connection, name, canonical_test_role=True)
        connection.close()


def _runtime_connection(database_url: str, role_name: str, schema_name: str | None = None):
    """Return a connection whose session authorization is the requested runtime role."""
    connection = connect_attested(database_url)
    connection.cursor_factory = OwnedRoleCursor
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role_name)))
        if schema_name is not None:
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
    connection.autocommit = False
    return connection


@pytest.mark.integration
def test_preexisting_role_collision_is_not_modified_or_adopted() -> None:
    """A colliding role and its membership state remain intact during allocation."""
    database_url = _ephemeral_database_url()
    collision_name = role_name_candidate("collision", "sentinel_role")
    grantee_name = f"fdbt_{invocation_id()}_sentinel_grantee_{uuid4().hex[:8]}"
    connection = connect_attested(database_url)
    role_oid = grantee_oid = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN CREATEROLE NOCREATEDB INHERIT CONNECTION LIMIT 7").format(
                    sql.Identifier(collision_name)
                )
            )
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(grantee_name)))
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (collision_name,))
            role_oid = int(cursor.fetchone()[0])
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (grantee_name,))
            grantee_oid = int(cursor.fetchone()[0])
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier(grantee_name),
                    sql.Identifier(collision_name),
                )
            )

        before = _role_and_membership_snapshot(connection, role_oid)
        allocated = allocate_role_names(connection, {"collision": "sentinel_role"})["collision"]
        assert allocated != collision_name
        assert _role_and_membership_snapshot(connection, role_oid) == before
    finally:
        try:
            with connection.cursor() as cursor:
                if role_oid is not None:
                    cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (collision_name,))
                    current = cursor.fetchone()
                    assert current is not None
                    assert int(current[0]) == role_oid
                if grantee_oid is not None:
                    cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (grantee_name,))
                    current = cursor.fetchone()
                    assert current is not None
                    assert int(current[0]) == grantee_oid
                    cursor.execute(
                        sql.SQL("REVOKE {} FROM {}").format(
                            sql.Identifier(grantee_name),
                            sql.Identifier(collision_name),
                        )
                    )
                    cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(collision_name)))
                    cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(grantee_name)))
        finally:
            connection.close()


@pytest.mark.integration
def test_multi_role_drop_rejected_without_changing_preexisting_second_role() -> None:
    """An absent first name cannot authorize dropping a pre-existing sentinel."""
    database_url = _ephemeral_database_url()
    sentinel = f"fdbt_{invocation_id()}_sentinel_{uuid4().hex[:8]}"
    absent = f"fdbt_{invocation_id()}_absent_{uuid4().hex[:8]}"
    with attested_connection(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN INHERIT CONNECTION LIMIT 7").format(sql.Identifier(sentinel))
            )
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (sentinel,))
            oid = int(cursor.fetchone()[0])
            cursor.execute(sql.SQL("GRANT {} TO test WITH ADMIN OPTION").format(sql.Identifier(sentinel)))
        before = _role_and_membership_snapshot(connection, oid)
        with connection.cursor(cursor_factory=OwnedRoleCursor) as guarded:
            statement = sql.SQL("DROP ROLE IF EXISTS {}, {}").format(sql.Identifier(absent), sql.Identifier(sentinel))
            with pytest.raises(DisposableTargetError, match="multi-role"):
                guarded.execute(statement)
            guarded.execute("SELECT %s::int", (7,))
            assert guarded.fetchone() == (7,)
            guarded.execute(query="SELECT %s::int", vars=(8,))
            assert guarded.fetchone() == (8,)
            guarded.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(absent)))
        assert _role_and_membership_snapshot(connection, oid) == before
        # The uncommitted sentinel/membership are rolled back on connection close.


def _role_and_membership_snapshot(connection, role_oid: int) -> tuple[tuple, tuple]:
    """Capture role attributes and all memberships touching the colliding role."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolreplication, "
            "rolinherit, rolconnlimit, rolvaliduntil, rolconfig FROM pg_roles WHERE oid = %s",
            (role_oid,),
        )
        attributes = cursor.fetchone()
        cursor.execute(
            "SELECT roleid, member, grantor, admin_option"
            + (", inherit_option, set_option" if connection.server_version >= 160000 else "")
            + " FROM pg_auth_members "
            "WHERE roleid = %s OR member = %s ORDER BY roleid, member, grantor",
            (role_oid, role_oid),
        )
        memberships = tuple(cursor.fetchall())
    return attributes, memberships


def _grant_usable_membership(cursor, capability_role: str, login_name: str) -> None:
    """Retain native membership semantics on each supported PostgreSQL version."""
    options = " WITH INHERIT TRUE, SET TRUE" if cursor.connection.server_version >= 160000 else ""
    cursor.execute(
        sql.SQL("GRANT {} TO {}" + options).format(sql.Identifier(capability_role), sql.Identifier(login_name))
    )


def _drop_roles(database_url: str, *role_names: str) -> None:
    """Drop disposable authority-test roles after their object grants have been removed."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for role_name in role_names:
            if owned_role_oid(role_name) is None:
                continue
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


def _restore_capability_membership(
    database_url: str,
    capability_role: str,
    member_role: str,
    grantor_role: str,
    previous_membership: tuple[bool, bool, bool] | None,
) -> None:
    """Restore only this grantor's prior capability membership and options."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        if previous_membership is None:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_auth_members AS membership "
                "JOIN pg_roles AS capability ON capability.oid = membership.roleid "
                "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                "JOIN pg_roles AS grantor ON grantor.oid = membership.grantor "
                "WHERE capability.rolname = %s AND grantee.rolname = %s AND grantor.rolname = %s)",
                (capability_role, member_role, grantor_role),
            )
            if not cursor.fetchone()[0]:
                return
            cursor.execute(
                sql.SQL("REVOKE {} FROM {} GRANTED BY {} RESTRICT").format(
                    sql.Identifier(capability_role),
                    sql.Identifier(member_role),
                    sql.Identifier(grantor_role),
                )
            )
            return

        admin_option, inherit_option, set_option = previous_membership
        cursor.execute(
            sql.SQL("GRANT {} TO {} WITH ADMIN {}, INHERIT {}, SET {} GRANTED BY {}").format(
                sql.Identifier(capability_role),
                sql.Identifier(member_role),
                sql.SQL("TRUE" if admin_option else "FALSE"),
                sql.SQL("TRUE" if inherit_option else "FALSE"),
                sql.SQL("TRUE" if set_option else "FALSE"),
                sql.Identifier(grantor_role),
            )
        )


def _drop_schema(database_url: str, schema_name: str) -> None:
    """Drop one disposable authority-test schema and all objects it owns."""
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))


def _move_capability_roles_aside(database_url: str) -> tuple[dict[str, str], set[str]]:
    """Temporarily rename existing disposable-cluster capability roles for bootstrap coverage."""
    import api.database as api_database

    role_backups = {
        api_database.AUTH_RUNTIME_ROLE: f"fdbt_{invocation_id()}_saved_auth_{uuid4().hex[:8]}",
        GRAPH_RUNTIME_ROLE: f"fdbt_{invocation_id()}_saved_graph_{uuid4().hex[:8]}",
        COORDINATION_RUNTIME_ROLE: f"fdbt_{invocation_id()}_saved_coord_{uuid4().hex[:8]}",
    }
    moved: set[str] = set()
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        for original, backup in role_backups.items():
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (backup,))
            if cursor.fetchone()[0]:
                pytest.fail(f"disposable PostgreSQL contains stale bootstrap backup role {backup}")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (original,))
            if cursor.fetchone()[0]:
                cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (original,))
                _CAPABILITY_BACKUP_OIDS[backup] = int(cursor.fetchone()[0])
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
                expected_oid = _CAPABILITY_BACKUP_OIDS.get(backup)
                cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (backup,))
                backup_row = cursor.fetchone()
                if expected_oid is None or backup_row is None or int(backup_row[0]) != expected_oid:
                    raise RuntimeError("capability role name/OID changed before prior-state restoration")
                cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(original)))
                cursor.execute(
                    sql.SQL("ALTER ROLE {} RENAME TO {}").format(
                        sql.Identifier(backup),
                        sql.Identifier(original),
                    )
                )
                _CAPABILITY_BACKUP_OIDS.pop(backup, None)


def _prepare_auth_schema(database_url: str) -> None:
    """Build the auth schema through the explicit PostgreSQL profile ledger."""
    _apply_auth_ledger(database_url)


def _apply_auth_ledger(database_url: str) -> None:
    """Apply capability bootstrap SQL and one selected profile ledger to disposable PostgreSQL."""
    _apply_ledger_profile(database_url, "auth")


def _apply_ledger_profile(database_url: str, profile: str) -> None:
    """Provision schema only through the selected validated profile ledger."""
    from scripts.postgresql_ledger import PlannedTarget, apply_profile_to_database, load_and_validate_manifest

    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        execute_capability_bootstrap(cursor)

    manifest = load_and_validate_manifest()
    target = PlannedTarget(
        logical_targets=(profile,),
        profile=profile,
        lineage="fresh-v1",
        execution_class="loopback",
        fingerprint="0" * 64,
        database_url=database_url,
    )
    with ContainerCliRunner(database_url) as runner:
        apply_profile_to_database(target, manifest, runner=runner)
    verify_applied_profile(database_url, manifest, profile)


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

    def _verify_runtime(error: str | None = None) -> None:
        """Verify the disposable auth login with an optional expected failure."""
        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
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
            cursor.execute(role_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"])))
            cursor.execute(role_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_MEMBERSHIP_BRIDGE_ROLE"])))
            cursor.execute(
                sql.SQL("GRANT UPDATE (hashed_password) ON TABLE user_credentials TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"])
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
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime()

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET FALSE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE {} FROM {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_MEMBERSHIP_BRIDGE_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"]),
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_MEMBERSHIP_BRIDGE_ROLE"]),
                )
            )
        _verify_runtime("retains schema-migration authority")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_MEMBERSHIP_BRIDGE_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
        _verify_runtime()
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE UPDATE (hashed_password) ON TABLE user_credentials FROM {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"])
                )
            )
        _drop_roles(
            database_url,
            _AUTH_RUNTIME_LOGIN,
            _ROLE_ALLOCATION.names["_AUTH_MEMBERSHIP_BRIDGE_ROLE"],
            _ROLE_ALLOCATION.names["_AUTH_USABLE_PATH_ROLE"],
        )


@pytest.mark.integration
@pytest.mark.parametrize("attack_role", ["replication", "credential_update"])
def test_auth_runtime_rejects_assumable_privileged_roles(attack_role: str) -> None:
    """NOINHERIT does not make a SET ROLE-reachable replication/write role safe."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    elevated_role = (
        _ROLE_ALLOCATION.names["_AUTH_REPLICATION_ROLE"]
        if attack_role == "replication"
        else _ROLE_ALLOCATION.names["_AUTH_WRITE_ROLE"]
    )
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
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"),
        ):
            api_database.verify_runtime_authority()
    finally:
        if attack_role == "credential_update":
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE UPDATE (hashed_password) ON TABLE user_credentials FROM {}").format(
                        sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_WRITE_ROLE"])
                    )
                )
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, elevated_role)


@pytest.mark.integration
def test_auth_runtime_rejects_unexpected_assumable_ordinary_role() -> None:
    """The auth login may assume only fardb_runtime_auth."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    import api.database as api_database

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))

            ordinary_role_ddl = sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(ordinary_role_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_ORDINARY_ROLE"])))

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_ORDINARY_ROLE"]),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="capability memberships are incompatible"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, _ROLE_ALLOCATION.names["_AUTH_ORDINARY_ROLE"])


@pytest.mark.integration
def test_auth_runtime_rejects_capability_create_on_non_current_schema() -> None:
    """Auth provisioning and startup reject capability CREATE on any schema."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)
    import api.database as api_database

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
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_UNRELATED_SCHEMA"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_UNRELATED_SCHEMA"]),
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                )
            )

        with (
            api_database.bind_database_url(database_url),
            pytest.raises(SchemaCompatibilityError, match="API runtime capability contract is incompatible"),
        ):
            api_database.verify_runtime_access_catalog()

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_schema(database_url, _ROLE_ALLOCATION.names["_AUTH_UNRELATED_SCHEMA"])
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN)


@pytest.mark.integration
def test_auth_runtime_rejects_inert_creator_admin_option() -> None:
    """An inert creator with ADMIN OPTION can re-delegate the auth capability."""
    database_url = _ephemeral_database_url()
    _prepare_auth_schema(database_url)

    import api.database as api_database

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            cursor.execute(
                runtime_login_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_INERT_CREATOR_LOGIN"]))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION, INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_AUTH_INERT_CREATOR_LOGIN"]),
                )
            )

        with (
            api_database.bind_database_url(database_url),
            pytest.raises(SchemaCompatibilityError, match="API runtime capability contract is incompatible"),
        ):
            api_database.verify_runtime_access_catalog()

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"),
        ):
            api_database.verify_runtime_authority()
    finally:
        _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, _ROLE_ALLOCATION.names["_AUTH_INERT_CREATOR_LOGIN"])


@pytest.mark.integration
def test_db_owner_admin_option_accepted_for_capability_roles() -> None:
    """Database owner ADMIN OPTION on capability roles is accepted while non-owner ADMIN OPTION is rejected."""
    database_url = _ephemeral_database_url()
    _apply_auth_ledger(database_url)

    import api.database as api_database

    non_owner_role = f"fdbt_{invocation_id()}_non_owner_{uuid4().hex[:8]}"
    db_owner: str | None = None
    owner_membership_grantor: str | None = None
    owner_membership_before: tuple[bool, bool, bool] | None = None
    owner_membership_captured = False
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(runtime_login_ddl.format(sql.Identifier(_AUTH_RUNTIME_LOGIN)))
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(_AUTH_RUNTIME_LOGIN),
                )
            )
            # Grant ADMIN OPTION to the current database owner role
            cursor.execute(
                "SELECT owner.rolname FROM pg_database AS database "
                "JOIN pg_roles AS owner ON owner.oid = database.datdba "
                "WHERE database.datname = current_database()"
            )
            db_owner = cursor.fetchone()[0]
            # PostgreSQL records superuser-issued role memberships under bootstrap superuser OID 10.
            cursor.execute("SELECT rolname FROM pg_roles WHERE oid = 10")
            owner_membership_grantor = cursor.fetchone()[0]
            cursor.execute(
                "SELECT membership.admin_option, membership.inherit_option, membership.set_option "
                "FROM pg_auth_members AS membership "
                "JOIN pg_roles AS capability ON capability.oid = membership.roleid "
                "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                "JOIN pg_roles AS grantor ON grantor.oid = membership.grantor "
                "WHERE capability.rolname = %s AND grantee.rolname = %s AND grantor.rolname = %s",
                (api_database.AUTH_RUNTIME_ROLE, db_owner, owner_membership_grantor),
            )
            owner_membership_before = cursor.fetchone()
            owner_membership_captured = True
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(db_owner),
                )
            )

        # 1. Database owner ADMIN OPTION is accepted
        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
        ):
            api_database.verify_runtime_authority()

        # 2. Non-owner ADMIN OPTION is rejected
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                    sql.Identifier(non_owner_role)
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier(api_database.AUTH_RUNTIME_ROLE),
                    sql.Identifier(non_owner_role),
                )
            )

        with (
            patch.object(api_database, "DATABASE_TYPE", "postgresql"),
            patch.object(
                api_database,
                "_create_postgres_connection",
                side_effect=lambda **_kwargs: _runtime_connection(database_url, _AUTH_RUNTIME_LOGIN),
            ),
            pytest.raises(SchemaCompatibilityError, match="capability contract is incompatible"),
        ):
            api_database.verify_runtime_authority()
    finally:
        try:
            _drop_roles(database_url, _AUTH_RUNTIME_LOGIN, non_owner_role)
        finally:
            if db_owner is not None and owner_membership_grantor is not None and owner_membership_captured:
                _restore_capability_membership(
                    database_url,
                    api_database.AUTH_RUNTIME_ROLE,
                    db_owner,
                    owner_membership_grantor,
                    owner_membership_before,
                )

    if db_owner is not None and owner_membership_grantor is not None and owner_membership_captured:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT membership.admin_option, membership.inherit_option, membership.set_option "
                "FROM pg_auth_members AS membership "
                "JOIN pg_roles AS capability ON capability.oid = membership.roleid "
                "JOIN pg_roles AS grantee ON grantee.oid = membership.member "
                "JOIN pg_roles AS grantor ON grantor.oid = membership.grantor "
                "WHERE capability.rolname = %s AND grantee.rolname = %s AND grantor.rolname = %s",
                (api_database.AUTH_RUNTIME_ROLE, db_owner, owner_membership_grantor),
            )
            restored_membership = cursor.fetchone()
        assert restored_membership == owner_membership_before


@pytest.mark.integration
def test_non_superuser_migration_owner_cannot_create_missing_capability_role() -> None:
    """A CREATEROLE migration owner cannot run the superuser-only capability bootstrap."""
    database_url = _ephemeral_database_url()
    role_backups: dict[str, str] = {}
    moved_roles: set[str] = set()
    capability_roles = {
        GRAPH_RUNTIME_CAPABILITY: GRAPH_RUNTIME_ROLE,
        COORDINATION_RUNTIME_CAPABILITY: COORDINATION_RUNTIME_ROLE,
    }

    try:
        _apply_ledger_profile(database_url, "graph")
        role_backups, moved_roles = _move_capability_roles_aside(database_url)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB CREATEROLE " "NOBYPASSRLS NOREPLICATION").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_MISSING_ROLE_MIGRATION_OWNER"])
                )
            )
        migration_owner = _runtime_connection(database_url, _ROLE_ALLOCATION.names["_MISSING_ROLE_MIGRATION_OWNER"])
        try:
            with migration_owner.cursor() as cursor:
                with pytest.raises(
                    psycopg2.Error,
                    match="FarDB capability-role bootstrap requires a PostgreSQL superuser",
                ):
                    execute_capability_bootstrap(cursor)
        finally:
            migration_owner.close()

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM pg_roles WHERE rolname = ANY(%s)",
                (list(capability_roles.values()),),
            )
            assert cursor.fetchone()[0] == 0
    finally:
        _drop_roles(database_url, _ROLE_ALLOCATION.names["_MISSING_ROLE_MIGRATION_OWNER"])
        if role_backups:
            _restore_capability_roles(database_url, role_backups, moved_roles)


@pytest.mark.integration
def test_superuser_bootstrap_enables_least_privilege_migration_and_runtime_verification() -> None:
    """Bootstrap creates safe roles consumed by migration and restricted runtimes."""
    database_url = _ephemeral_database_url()
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
                    sql.Identifier(_ROLE_ALLOCATION.names["_BOOTSTRAP_MIGRATION_OWNER"])
                )
            )

        creator_connection = _runtime_connection(database_url, _ROLE_ALLOCATION.names["_BOOTSTRAP_MIGRATION_OWNER"])
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
                (GRAPH_RUNTIME_ROLE, _ROLE_ALLOCATION.names["_BOOTSTRAP_MIGRATION_OWNER"]),
            )
            assert cursor.fetchone()[0] == 1
            execute_capability_bootstrap(cursor)
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
                (GRAPH_RUNTIME_ROLE, _ROLE_ALLOCATION.names["_BOOTSTRAP_MIGRATION_OWNER"]),
            )
            assert cursor.fetchone()[0] == 0
        capabilities = {GRAPH_RUNTIME_CAPABILITY, COORDINATION_RUNTIME_CAPABILITY}
        _apply_ledger_profile(database_url, "combined")

        import api.database as api_database

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
                side_effect=lambda **_kwargs: _runtime_connection(
                    database_url,
                    _BOOTSTRAP_AUTH_RUNTIME_LOGIN,
                ),
            ),
        ):
            api_database.verify_schema_compatibility()
            api_database.verify_runtime_access_catalog()
            api_database.verify_runtime_authority()
    finally:
        if graph_runtime_engine is not None:
            graph_runtime_engine.dispose()
        _drop_roles(
            database_url,
            _BOOTSTRAP_GRAPH_RUNTIME_LOGIN,
            _BOOTSTRAP_AUTH_RUNTIME_LOGIN,
            _ROLE_ALLOCATION.names["_BOOTSTRAP_MIGRATION_OWNER"],
        )
        if role_backups:
            database_name = urlsplit(database_url).path.lstrip("/")
            if database_name not in _ISOLATED_DATABASE_ADMIN_URLS:
                pytest.fail("isolated database role restoration target is unavailable")
            _DEFERRED_CAPABILITY_ROLE_RESTORATIONS[database_name] = (role_backups, moved_roles)


@pytest.mark.integration
def test_capability_bootstrap_rejects_create_on_non_current_schema() -> None:
    """A capability role may not retain CREATE on any schema in the database."""
    database_url = _ephemeral_database_url()

    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            execute_capability_bootstrap(cursor)
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_BOOTSTRAP_UNRELATED_SCHEMA"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_BOOTSTRAP_UNRELATED_SCHEMA"]),
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                )
            )
            cursor.execute("SELECT current_schema()")
            assert cursor.fetchone()[0] != _ROLE_ALLOCATION.names["_BOOTSTRAP_UNRELATED_SCHEMA"]

            with pytest.raises(psycopg2.Error, match="unsafe FarDB capability role"):
                execute_capability_bootstrap(cursor)
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_BOOTSTRAP_UNRELATED_SCHEMA"])
                )
            )


@pytest.mark.integration
def test_graph_runtime_rejects_capability_create_on_non_current_schema() -> None:
    """Graph provisioning, catalog, and startup reject CREATE on any schema."""
    database_url = _ephemeral_database_url()
    operator_engine = create_attested_engine(database_url, future=True)
    runtime_engine = None

    try:
        _apply_ledger_profile(database_url, "graph")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
                )
            )
            cursor.execute(
                sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_UNRELATED_SCHEMA"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_UNRELATED_SCHEMA"]),
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                )
            )

        with (
            operator_engine.connect() as connection,
            pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"),
        ):
            _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
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
        _drop_schema(database_url, _ROLE_ALLOCATION.names["_GRAPH_UNRELATED_SCHEMA"])
        _drop_roles(database_url, _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"])
        operator_engine.dispose()


@pytest.mark.integration
def test_runtime_database_authority_rejects_capability_reachable_through_superuser_role() -> None:
    """A login may not reach a capability through an intermediate superuser role."""
    database_url = _ephemeral_database_url()
    operator_engine = create_attested_engine(database_url, future=True)
    runtime_engine = None

    try:
        _apply_ledger_profile(database_url, "graph")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]))
            )
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"]))
            )
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN INHERIT SUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
                ).format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_SUPERUSER_ROLE"]))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_SUPERUSER_ROLE"]),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"]),
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET FALSE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_SUPERUSER_ROLE"]),
                )
            )

        with (
            operator_engine.connect() as connection,
            pytest.raises(SchemaCompatibilityError, match="unsafe or missing runtime capability role"),
        ):
            _verify_runtime_capability_catalog(connection, (GRAPH_RUNTIME_CAPABILITY,))

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
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
            _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"],
            _ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"],
            _ROLE_ALLOCATION.names["_GRAPH_SUPERUSER_ROLE"],
        )
        operator_engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("membership_posture", ["delegable", "usable"])
def test_runtime_database_authority_rejects_unsafe_capability_grantee(membership_posture: str) -> None:
    """No other login may delegate or use an application capability."""
    database_url = _ephemeral_database_url()
    operator_engine = create_attested_engine(database_url, future=True)
    runtime_engine = None

    try:
        _apply_ledger_profile(database_url, "graph")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if int(cursor.fetchone()[0]) < 160000:
                pytest.skip("per-membership INHERIT and SET options require PostgreSQL 16+")
            runtime_login_ddl = sql.SQL(
                "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(
                runtime_login_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]))
            )
            cursor.execute(
                runtime_login_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"]))
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
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
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"]),
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
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
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
            _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"],
            _ROLE_ALLOCATION.names["_GRAPH_OTHER_CAPABILITY_LOGIN"],
        )
        operator_engine.dispose()


@pytest.mark.integration
def test_capability_catalog_verification_has_bounded_round_trips() -> None:
    """The full two-capability grant matrix must remain set-based."""
    database_url = _ephemeral_database_url()
    operator_engine = create_attested_engine(database_url, future=True)
    statement_count = 0
    runtime_login_created = False

    def _count_statement(*_args, **_kwargs) -> None:
        """Count driver executions inside the focused catalog verification window."""
        nonlocal statement_count
        statement_count += 1

    try:
        _apply_ledger_profile(database_url, "combined")
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_BOOTSTRAP_GRAPH_RUNTIME_LOGIN)))
            runtime_login_created = True
            for role_name in (GRAPH_RUNTIME_ROLE, COORDINATION_RUNTIME_ROLE):
                _grant_usable_membership(cursor, role_name, _BOOTSTRAP_GRAPH_RUNTIME_LOGIN)
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
        if runtime_login_created:
            _drop_roles(database_url, _BOOTSTRAP_GRAPH_RUNTIME_LOGIN)
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
    operator_engine = create_attested_engine(database_url, future=True)
    original_owner: str | None = None

    try:
        _apply_ledger_profile(database_url, "graph")

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
        ("ordinary", "NOREPLICATION", "capability memberships are incompatible"),
        ("replication", "REPLICATION", "retains schema-migration authority"),
    ],
)
def test_runtime_database_authority_rejects_unexpected_assumable_role_without_capabilities(
    assumable_role: str,
    role_attribute: str,
    expected_error: str,
) -> None:
    """A no-capability runtime login may not retain any assumable role membership."""
    database_url = _ephemeral_database_url()
    assumable_role = (
        _ROLE_ALLOCATION.names["_GRAPH_ORDINARY_ROLE"]
        if assumable_role == "ordinary"
        else _ROLE_ALLOCATION.names["_GRAPH_REPLICATION_ROLE"]
    )
    runtime_engine = None
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_RUNTIME_LOGIN"]))
            )

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
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_RUNTIME_LOGIN"]),
                )
            )

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_GRAPH_NO_CAP_RUNTIME_LOGIN"]),
            future=True,
        )
        with pytest.raises(SchemaCompatibilityError, match=expected_error):
            verify_runtime_database_authority(runtime_engine)
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        _drop_roles(database_url, _ROLE_ALLOCATION.names["_GRAPH_NO_CAP_RUNTIME_LOGIN"], assumable_role)


@pytest.mark.integration
def test_runtime_database_authority_enforces_zero_managed_privileges_without_capabilities() -> None:
    """A no-capability login may hold no managed table, column, or sequence privilege."""
    database_url = _ephemeral_database_url()
    operator_engine = create_attested_engine(database_url, future=True)
    runtime_engine = None
    sequence_name: str | None = None

    try:
        _apply_ledger_profile(database_url, "combined")
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"]))
            )
            cursor.execute("SELECT pg_get_serial_sequence('asset_relationships', 'id')")
            sequence_name = cursor.fetchone()[0]
            assert isinstance(sequence_name, str)
            assert sequence_name

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"]),
            future=True,
        )

        verify_runtime_database_authority(runtime_engine)

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT INSERT ON TABLE assets TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                )
            )
        with pytest.raises(SchemaCompatibilityError, match="runtime login grants are incompatible on assets"):
            verify_runtime_database_authority(runtime_engine)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE INSERT ON TABLE assets FROM {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT UPDATE (price) ON TABLE assets TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                )
            )
        with pytest.raises(SchemaCompatibilityError, match="runtime login grants are incompatible on assets"):
            verify_runtime_database_authority(runtime_engine)
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("REVOKE UPDATE (price) ON TABLE assets FROM {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(*sequence_name.split(".")),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"]),
                )
            )
        with pytest.raises(
            SchemaCompatibilityError, match="runtime login grants are incompatible on asset_relationships"
        ):
            verify_runtime_database_authority(runtime_engine)
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        if sequence_name is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON TABLE assets FROM {}").format(
                        sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE UPDATE (price) ON TABLE assets FROM {}").format(
                        sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM {}").format(
                        sql.Identifier(*sequence_name.split(".")),
                        sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"]),
                    )
                )
        _drop_roles(database_url, _ROLE_ALLOCATION.names["_GRAPH_NO_CAP_DIRECT_LOGIN"])
        operator_engine.dispose()


@pytest.mark.integration
def test_runtime_database_authority_rejects_unexpected_assumable_truncate_role() -> None:
    """Unexpected role membership cannot retain whole-table write authority."""
    database_url = _ephemeral_database_url()
    operator_engine = None
    runtime_engine = None
    extra_role_created = False

    try:
        operator_engine = create_attested_engine(database_url, future=True)
        _apply_ledger_profile(database_url, "graph")

        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                _RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]))
            )

            extra_role_ddl = sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
            )
            cursor.execute(extra_role_ddl.format(sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_TRUNCATE_ROLE"])))
            extra_role_created = True

            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
                )
            )
            cursor.execute(
                sql.SQL("GRANT TRUNCATE ON TABLE assets TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_TRUNCATE_ROLE"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_TRUNCATE_ROLE"]),
                    sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"]),
                )
            )

        runtime_engine = create_engine(
            "postgresql+psycopg2://",
            creator=lambda: _runtime_connection(
                database_url,
                _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"],
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
                        sql.Identifier(_ROLE_ALLOCATION.names["_GRAPH_EXTRA_TRUNCATE_ROLE"])
                    )
                )

        _drop_roles(
            database_url,
            _ROLE_ALLOCATION.names["_GRAPH_EXTRA_RUNTIME_LOGIN"],
            _ROLE_ALLOCATION.names["_GRAPH_EXTRA_TRUNCATE_ROLE"],
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
        operator_engine = create_attested_engine(database_url, future=True)
        _apply_ledger_profile(database_url, "graph")

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
    operator_engine = create_attested_engine(database_url, future=True)
    _apply_ledger_profile(database_url, "graph")

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
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"])
                )
            )
            cursor.execute(_RUNTIME_LOGIN_DDL.format(sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_RUNTIME_LOGIN"])))
            cursor.execute(
                sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"])
                )
            )
            cursor.execute(
                sql.SQL("ALTER TABLE asset_relationships OWNER TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"])
                )
            )
            cursor.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"]),
                    sql.Identifier(_ROLE_ALLOCATION.names["_SEQUENCE_RUNTIME_LOGIN"]),
                )
            )

            cursor.execute(
                "SELECT pg_get_userbyid(relowner) FROM pg_class "
                "WHERE oid = pg_get_serial_sequence('asset_relationships', 'id')::regclass"
            )
            assert cursor.fetchone()[0] == _ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"]
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
            creator=lambda: _runtime_connection(database_url, _ROLE_ALLOCATION.names["_SEQUENCE_RUNTIME_LOGIN"]),
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
        _drop_roles(
            database_url,
            _ROLE_ALLOCATION.names["_SEQUENCE_RUNTIME_LOGIN"],
            _ROLE_ALLOCATION.names["_SEQUENCE_OWNER_ROLE"],
        )
        operator_engine.dispose()


def test_bootstrap_preserves_each_separately_owned_target_membership() -> None:
    """Repeated bootstrap preserves target owners with complete version-specific options."""
    database_url = _ephemeral_database_url()
    databases = []
    names = []
    with _operator_connection(database_url) as connection:
        allocated = allocate_role_names(
            connection, {key: f"cq1608_target_{key}" for key in ("auth", "graph", "coordination")}
        )
    try:
        _apply_ledger_profile(database_url, "auth")
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            supports_options = int(cursor.fetchone()[0]) >= 160000
            mapping = {}
            snapshots = {}
            for component, role_name in allocated.items():
                cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role_name)))
                names.append(role_name)
                database = f"fdbt_owner_{invocation_id()[:12]}_{component}_{uuid4().hex[:8]}"
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(role_name))
                )
                databases.append(database)
                capability = f"fardb_runtime_{component}"
                mapping[capability] = [database]
                cursor.execute(
                    sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                        sql.Identifier(capability), sql.Identifier(role_name)
                    )
                )
                if supports_options:
                    cursor.execute(
                        sql.SQL("GRANT {} TO {} WITH ADMIN TRUE, INHERIT FALSE, SET FALSE").format(
                            sql.Identifier(capability), sql.Identifier(role_name)
                        )
                    )
                cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role_name,))
                snapshots[role_name] = _role_and_membership_snapshot(connection, int(cursor.fetchone()[0]))
            # Ownership of the auth target does not exempt a coordination grant.
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier(COORDINATION_RUNTIME_ROLE), sql.Identifier(allocated["auth"])
                )
            )
            for _ in range(2):
                execute_capability_bootstrap(cursor, mapping)
                cursor.execute(
                    "SELECT count(*) FROM pg_auth_members AS membership "
                    "JOIN pg_roles AS role ON role.oid=membership.roleid "
                    "JOIN pg_roles AS member ON member.oid=membership.member "
                    "WHERE role.rolname=%s AND member.rolname=%s",
                    (COORDINATION_RUNTIME_ROLE, allocated["auth"]),
                )
                assert cursor.fetchone()[0] == 0
                for role_name, expected in snapshots.items():
                    cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role_name,))
                    assert _role_and_membership_snapshot(connection, int(cursor.fetchone()[0])) == expected
    finally:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            for database in databases:
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
        _drop_roles(database_url, *names)


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {},
        {"fardb_runtime_auth": ["missing_database"]},
        {
            name: ["missing_database"]
            for name in ("fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination")
        },
    ],
)
def test_invalid_bootstrap_mapping_rolls_back_transaction_mutations(invalid) -> None:
    """Mapping rejection rolls back the same transaction, including preceding role creation."""
    database_url = _ephemeral_database_url()
    with _operator_connection(database_url) as connection:
        name = allocate_role_names(connection, {"sentinel": "cq1608_rollback_sentinel"})["sentinel"]
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
            mapping = invalid if invalid is not None else {"fardb_runtime_auth": []}
            with pytest.raises(psycopg2.Error, match="bootstrap target"):
                execute_capability_bootstrap(cursor, mapping)
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (name,))
            assert cursor.fetchone() is None
            cursor.execute("SELECT NULLIF(current_setting('fardb.bootstrap_targets', true), '')")
            assert cursor.fetchone()[0] is None


def test_bootstrap_failure_after_first_capability_creation_rolls_back_every_role() -> None:
    """An unsafe later capability cannot leave an earlier created capability behind."""
    database_url = _ephemeral_database_url()
    _apply_ledger_profile(database_url, "auth")
    backups, moved = _move_capability_roles_aside(database_url)
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN CREATEDB").format(sql.Identifier(GRAPH_RUNTIME_ROLE)))
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (GRAPH_RUNTIME_ROLE,))
            graph_oid = int(cursor.fetchone()[0])
            before = _role_and_membership_snapshot(connection, graph_oid)
            with pytest.raises(psycopg2.Error, match="unsafe FarDB capability role"):
                execute_capability_bootstrap(cursor)
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                (["fardb_runtime_auth", "fardb_runtime_coordination"],),
            )
            assert cursor.fetchall() == []
            assert _role_and_membership_snapshot(connection, graph_oid) == before
    finally:
        _restore_capability_roles(database_url, backups, moved)


def test_bootstrap_restricted_revocation_rolls_back_and_preserves_dependent_owner() -> None:
    """A tracked dependent owner grant cannot be removed by cascading bootstrap cleanup."""
    database_url = _ephemeral_database_url()
    _apply_ledger_profile(database_url, "auth")
    names = []
    owned_database = None
    with _operator_connection(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        if int(cursor.fetchone()[0]) < 160000:
            pytest.skip("PostgreSQL 16 tracks dependent role-membership grant chains")
        allocated = allocate_role_names(
            connection, {"delegator": "cq1608_delegator", "owner": "cq1608_dependent_owner"}
        )
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            for name in allocated.values():
                cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
                names.append(name)
            owned_database = f"fdbt_dependent_{uuid4().hex}"
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(owned_database), sql.Identifier(allocated["owner"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE), sql.Identifier(allocated["delegator"])
                )
            )
            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION GRANTED BY {}").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(allocated["owner"]),
                    sql.Identifier(allocated["delegator"]),
                )
            )
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (allocated["owner"],))
            oid = int(cursor.fetchone()[0])
            before = _role_and_membership_snapshot(connection, oid)
            mapping = {
                name: [urlsplit(database_url).path.lstrip("/")]
                for name in ("fardb_runtime_auth", "fardb_runtime_graph", "fardb_runtime_coordination")
            }
            mapping[GRAPH_RUNTIME_ROLE] = [owned_database]
            with pytest.raises(psycopg2.Error, match="dependent|depend on"):
                execute_capability_bootstrap(cursor, mapping)
            assert _role_and_membership_snapshot(connection, oid) == before
            # Explicit fixture cleanup removes the dependent edge before its grantor edge.
            cursor.execute(
                sql.SQL("REVOKE {} FROM {} GRANTED BY {} RESTRICT").format(
                    sql.Identifier(GRAPH_RUNTIME_ROLE),
                    sql.Identifier(allocated["owner"]),
                    sql.Identifier(allocated["delegator"]),
                )
            )
    finally:
        if owned_database is not None:
            with _operator_connection(database_url) as connection, connection.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(owned_database)))
        _drop_roles(database_url, *reversed(names))


def test_runtime_non_superuser_identity_and_startup_topology_use_same_connections() -> None:
    """Scoped logins prove shared identity while each authority check retains its own session."""
    from api import app_factory
    from src.data.postgresql_topology import read_database_identity

    database_url = _ephemeral_database_url()
    _apply_ledger_profile(database_url, "combined")
    names = []
    engines = []
    try:
        with _operator_connection(database_url) as connection, connection.cursor() as cursor:
            for login, capability in [
                ("fardb_login_graph", GRAPH_RUNTIME_ROLE),
                ("fardb_login_coordination", COORDINATION_RUNTIME_ROLE),
                ("fardb_login_auth", "fardb_runtime_auth"),
            ]:
                # This fixture exercises ordinary startup without an explicit SET ROLE.
                # INHERIT activates only the already-approved scoped capability membership
                # on both PG15 and PG16; no role elevation or authority predicate changes.
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE " "NOBYPASSRLS NOREPLICATION"
                    ).format(sql.Identifier(login))
                )
                names.append(login)
                cursor.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(capability), sql.Identifier(login)))
        graph = create_engine(
            "postgresql+psycopg2://", creator=lambda: _runtime_connection(database_url, "fardb_login_graph")
        )
        coordination = create_engine(
            "postgresql+psycopg2://", creator=lambda: _runtime_connection(database_url, "fardb_login_coordination")
        )
        engines.extend([graph, coordination])
        with graph.connect() as graph_connection, coordination.connect() as coordination_connection:
            assert read_database_identity(graph_connection) == read_database_identity(coordination_connection)
            for connection in (graph_connection, coordination_connection):
                assert (
                    connection.exec_driver_sql("SELECT rolsuper FROM pg_roles WHERE rolname=current_user").scalar()
                    is False
                )
        app_factory._verify_reconciliation_schemas(graph, coordination)
    finally:
        for engine in engines:
            engine.dispose()
        _drop_roles(database_url, *names)
