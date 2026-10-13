"""Live PostgreSQL verification for runtime capability SQL construction."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlsplit

import pytest

from api import database as api_database
from src.data import database as runtime_database
from tests.integration.postgresql_disposable_cluster import (
    DisposableTargetError,
    OwnedRole,
    connect_owned_attested,
    create_attested_engine,
    drop_owned_role,
    execute_capability_bootstrap,
    owned_role_oid,
)

pytestmark = pytest.mark.integration

_EPHEMERAL_AUTHORITY_FLAG = "FARDB_EPHEMERAL_POSTGRES_AUTHORITY_TESTS"
_EPHEMERAL_POSTGRES_URL = "FARDB_EPHEMERAL_POSTGRES_URL"
_TEST_POSTGRES_URL = "FARDB_POSTGRES_TEST_URL"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_loopback_postgres_url(url: str) -> bool:
    """Reject PostgreSQL URI overrides that can redirect a loopback URL to another host."""
    try:
        parsed = urlsplit(url)
        parameters = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return False
    host_override = any(name.casefold() in {"host", "hostaddr"} for name, _value in parameters)
    return (
        parsed.scheme.casefold() in {"postgres", "postgresql"}
        and parsed.hostname in _LOOPBACK_HOSTS
        and not host_override
    )


def _postgres_test_url() -> str:
    """Return the explicitly opted-in, loopback-only disposable PostgreSQL URL or skip the test."""
    if os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1":
        pytest.skip(f"Set {_EPHEMERAL_AUTHORITY_FLAG}=1 only for disposable PostgreSQL authority tests")

    url = os.getenv(_EPHEMERAL_POSTGRES_URL)
    if not url:
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} is required when {_EPHEMERAL_AUTHORITY_FLAG}=1")
    assert url is not None
    if not url.lower().startswith(("postgresql://", "postgres://")):
        pytest.fail(f"{_EPHEMERAL_POSTGRES_URL} must be a PostgreSQL URL")

    test_url = os.getenv(_TEST_POSTGRES_URL)
    if test_url and test_url != url:
        pytest.fail(f"{_TEST_POSTGRES_URL} must match {_EPHEMERAL_POSTGRES_URL} for this mutating integration test")
    if not _is_loopback_postgres_url(url):
        pytest.fail(
            f"{_EPHEMERAL_POSTGRES_URL} must target loopback and must not override host or hostaddr in query parameters"
        )

    return url


@pytest.mark.parametrize(
    "query",
    (
        "host=192.0.2.10",
        "hostaddr=192.0.2.10",
        "host=localhost&hostaddr=192.0.2.10",
        "%68ostaddr=192.0.2.10",
    ),
)
def test_loopback_postgres_guard_rejects_host_query_overrides(query: str) -> None:
    """Reject URI query options that can redirect an otherwise loopback connection."""
    url = f"postgresql://test:test@127.0.0.1:5432/test_db?{query}"

    assert not _is_loopback_postgres_url(url)


def test_loopback_postgres_guard_accepts_plain_loopback_authority() -> None:
    """Accept an ordinary loopback URI when no host override is present."""
    assert _is_loopback_postgres_url("postgresql://test:test@127.0.0.1:5432/test_db")


@dataclass(frozen=True)
class _AddedMembership:
    """Record the exact grant added by this invocation for fenced cleanup."""

    capability: OwnedRole
    login: OwnedRole
    grantor: OwnedRole
    options: tuple[bool, bool, bool]


@dataclass
class _BootstrapRoles:
    """Retain partial setup ownership so every failure can clean its own progress."""

    supports_options: bool = False
    logins: list[OwnedRole] = field(default_factory=list)
    memberships: list[_AddedMembership] = field(default_factory=list)


def _membership_options(cursor, membership: _AddedMembership):
    """Read only the recorded grantor edge with PG15/PG16-compatible options."""
    cursor.execute(
        "SELECT admin_option, COALESCE((to_jsonb(membership)->>'inherit_option')::boolean, TRUE), "
        "COALESCE((to_jsonb(membership)->>'set_option')::boolean, TRUE) "
        "FROM pg_auth_members AS membership WHERE roleid=%s AND member=%s AND grantor=%s",
        (membership.capability.oid, membership.login.oid, membership.grantor.oid),
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise DisposableTargetError("ambiguous fixture membership cleanup")
    return tuple(rows[0]) if rows else None


def _require_current_role(cursor, role: OwnedRole) -> None:
    """Reject name reuse before any membership or login cleanup mutation."""
    cursor.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role.name,))
    row = cursor.fetchone()
    if row is None or int(row[0]) != role.oid:
        raise DisposableTargetError("fixture role name/OID changed before cleanup")


def _validated_membership_cleanup(cursor, created_logins, created_memberships):
    """Validate every role and edge before returning an exact cleanup plan."""
    removable = []
    # Validate all recorded identities and options before the first mutation.
    for membership in created_memberships:
        for role in (membership.capability, membership.login, membership.grantor):
            _require_current_role(cursor, role)
        current = _membership_options(cursor, membership)
        if current is not None and current != membership.options:
            raise DisposableTargetError("fixture membership changed before cleanup")
        if current is not None:
            removable.append(membership)
    for role in created_logins:
        _require_current_role(cursor, role)
        if owned_role_oid(role.name) != role.oid:
            raise DisposableTargetError("fixture login is not invocation-owned")
    return removable


def _drop_logins(url: str, created_logins: list[OwnedRole], created_memberships: list[_AddedMembership]) -> None:
    """Restore only recorded added edges and drop only invocation-created login OIDs."""
    if not created_logins and not created_memberships:
        return
    from psycopg2 import sql

    conn = connect_owned_attested(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            removable = _validated_membership_cleanup(cursor, created_logins, created_memberships)
            for membership in removable:
                cursor.execute(
                    sql.SQL("REVOKE {} FROM {} GRANTED BY {} RESTRICT").format(
                        sql.Identifier(membership.capability.name),
                        sql.Identifier(membership.login.name),
                        sql.Identifier(membership.grantor.name),
                    )
                )
            for role in created_logins:
                if not drop_owned_role(conn, role):
                    raise DisposableTargetError("fixture login ownership changed during cleanup")
    finally:
        conn.close()


def _add_missing_runtime_login(cursor, login_role, capability_role, grantor, state: _BootstrapRoles) -> None:
    """Preserve an existing login and record only newly added setup state."""
    from psycopg2 import sql

    cursor.execute("SELECT oid, rolinherit FROM pg_roles WHERE rolname=%s", (login_role,))
    login_row = cursor.fetchone()
    if login_row is None:
        cursor.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB " "NOCREATEROLE NOBYPASSRLS NOREPLICATION"
            ).format(sql.Identifier(login_role))
        )
        oid = owned_role_oid(login_role)
        if oid is None:
            raise DisposableTargetError("new fixture login ownership was not recorded")
        login = OwnedRole(login_role, oid)
        inherits = False
        state.logins.append(login)
    else:
        login = OwnedRole(login_role, int(login_row[0]))
        inherits = bool(login_row[1])
    cursor.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (capability_role,))
    capability = OwnedRole(capability_role, int(cursor.fetchone()[0]))
    cursor.execute("SELECT 1 FROM pg_auth_members WHERE roleid=%s AND member=%s", (capability.oid, login.oid))
    if cursor.fetchone() is None:
        expected_options = (False, inherits if state.supports_options else True, True)
        membership = _AddedMembership(capability, login, grantor, expected_options)
        # Record the exact intended edge before execution, including error paths.
        state.memberships.append(membership)
        cursor.execute(
            sql.SQL("GRANT {} TO {} GRANTED BY {}").format(
                sql.Identifier(capability_role), sql.Identifier(login_role), sql.Identifier(grantor.name)
            )
        )
        options = _membership_options(cursor, membership)
        if options != expected_options:
            raise DisposableTargetError("new fixture membership differs from the requested edge")


def _ensure_bootstrap_roles(url: str) -> tuple[list[OwnedRole], list[_AddedMembership]]:
    """Bootstrap atomically and record only fixture-created roles and memberships."""
    if (
        os.getenv(_EPHEMERAL_AUTHORITY_FLAG) != "1"
        or url != os.getenv(_EPHEMERAL_POSTGRES_URL)
        or not _is_loopback_postgres_url(url)
    ):
        pytest.fail(
            "Capability-role bootstrap requires the opted-in loopback FARDB_EPHEMERAL_POSTGRES_URL "
            "without host or hostaddr query overrides"
        )
    state = _BootstrapRoles()
    conn = connect_owned_attested(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            execute_capability_bootstrap(cursor)
            cursor.execute("SHOW server_version_num")
            state.supports_options = int(cursor.fetchone()[0]) >= 160000
            cursor.execute("SELECT oid, rolname FROM pg_roles WHERE rolname=current_user")
            grantor_oid, grantor_name = cursor.fetchone()
            grantor = OwnedRole(grantor_name, int(grantor_oid))
            for login_role, capability_role in (
                ("fardb_login_auth", api_database.AUTH_RUNTIME_ROLE),
                ("fardb_login_graph", runtime_database.GRAPH_RUNTIME_ROLE),
            ):
                _add_missing_runtime_login(cursor, login_role, capability_role, grantor, state)
    except Exception:
        _drop_logins(url, state.logins, state.memberships)
        raise
    finally:
        conn.close()
    return state.logins, state.memberships


def test_runtime_capability_verifier_sql_executes_against_postgres() -> None:
    """Execute the real verifier SQL against PostgreSQL rather than only mocking it."""
    url = _postgres_test_url()
    created_logins, created_memberships = _ensure_bootstrap_roles(url)
    engine = None
    try:
        engine = create_attested_engine(url, future=True)
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


@pytest.mark.parametrize("url", [None, "", "sqlite:///not-postgresql", "postgresql://test@192.0.2.1/test_db"])
def test_postgres_test_url_preserves_invalid_target_failures(monkeypatch, url) -> None:
    """Explicit narrowing must preserve missing-value and target failure behaviour."""
    monkeypatch.setenv(_EPHEMERAL_AUTHORITY_FLAG, "1")
    monkeypatch.delenv(_TEST_POSTGRES_URL, raising=False)
    if url is None:
        monkeypatch.delenv(_EPHEMERAL_POSTGRES_URL, raising=False)
    else:
        monkeypatch.setenv(_EPHEMERAL_POSTGRES_URL, url)
    with pytest.raises(pytest.fail.Exception):
        _postgres_test_url()


def test_postgres_test_url_preserves_valid_target_and_mismatch_failure(monkeypatch) -> None:
    """Keep the original URL unchanged and reject conflicting mutating-test targets."""
    url = "postgresql://test@127.0.0.1/test_db"
    monkeypatch.setenv(_EPHEMERAL_AUTHORITY_FLAG, "1")
    monkeypatch.setenv(_EPHEMERAL_POSTGRES_URL, url)
    monkeypatch.delenv(_TEST_POSTGRES_URL, raising=False)
    assert _postgres_test_url() == url
    monkeypatch.setenv(_TEST_POSTGRES_URL, url + "_other")
    with pytest.raises(pytest.fail.Exception, match="must match"):
        _postgres_test_url()


@pytest.mark.parametrize("changed", ["capability", "login", "grantor", "options", "owned-login"])
def test_fixture_cleanup_rejects_changed_identity_before_any_mutation(monkeypatch, changed) -> None:
    """Role reuse or altered grant options cannot become a destructive cleanup target."""
    from unittest.mock import MagicMock

    membership = _AddedMembership(
        OwnedRole("capability", 1), OwnedRole("login", 2), OwnedRole("grantor", 3), (False, False, True)
    )
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    rows = [(1,), (2,), (3,), (2,)]
    positions = {"capability": 0, "login": 1, "grantor": 2}
    if changed in positions:
        rows[positions[changed]] = (999,)
    cursor.fetchone.side_effect = rows
    cursor.fetchall.return_value = [(True, False, True) if changed == "options" else membership.options]
    monkeypatch.setattr(sys.modules[__name__], "connect_owned_attested", lambda _url: connection)
    monkeypatch.setattr(sys.modules[__name__], "owned_role_oid", lambda _name: 999 if changed == "owned-login" else 2)
    with pytest.raises(DisposableTargetError):
        _drop_logins("target", [membership.login], [membership])
    assert all(
        isinstance(call.args[0], str) and call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list
    )
    connection.close.assert_called_once()


def test_fixture_cleanup_does_not_drop_a_preexisting_login(monkeypatch) -> None:
    """Restoring an added edge never turns an existing login into an owned drop target."""
    from unittest.mock import MagicMock

    membership = _AddedMembership(
        OwnedRole("capability", 1), OwnedRole("login", 2), OwnedRole("grantor", 3), (False, False, True)
    )
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(1,), (2,), (3,)]
    cursor.fetchall.return_value = [membership.options]
    monkeypatch.setattr(sys.modules[__name__], "connect_owned_attested", lambda _url: connection)
    drop = MagicMock()
    monkeypatch.setattr(sys.modules[__name__], "drop_owned_role", drop)
    _drop_logins("target", [], [membership])
    drop.assert_not_called()
    assert len(cursor.execute.call_args_list) == 5
    from psycopg2 import sql

    statement = cursor.execute.call_args_list[-1].args[0]
    assert [piece.string if isinstance(piece, sql.SQL) else piece.strings for piece in statement.seq] == [
        "REVOKE ",
        ("capability",),
        " FROM ",
        ("login",),
        " GRANTED BY ",
        ("grantor",),
        " RESTRICT",
    ]


def test_existing_login_collision_retains_attributes_and_prior_memberships() -> None:
    """The bootstrap caller restores its added edge without adopting an existing login."""
    from psycopg2 import sql

    url = _postgres_test_url()
    connection = connect_owned_attested(url)
    connection.autocommit = True
    sentinel = None
    created_logins: list[OwnedRole] = []
    created_memberships: list[_AddedMembership] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOINHERIT CONNECTION LIMIT 7").format(sql.Identifier("fardb_login_auth"))
            )
            oid = owned_role_oid("fardb_login_auth")
            if oid is None:
                raise DisposableTargetError("outer collision fixture was not recorded")
            sentinel = OwnedRole("fardb_login_auth", oid)
            cursor.execute("SELECT to_jsonb(role) FROM pg_roles AS role WHERE oid=%s", (oid,))
            before_role = cursor.fetchone()[0]
            cursor.execute(
                "SELECT to_jsonb(membership) FROM pg_auth_members AS membership WHERE member=%s ORDER BY roleid,grantor",
                (oid,),
            )
            before_memberships = cursor.fetchall()
        created_logins, created_memberships = _ensure_bootstrap_roles(url)
        assert sentinel not in created_logins
        _drop_logins(url, created_logins, created_memberships)
        created_logins = []
        created_memberships = []
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_jsonb(role) FROM pg_roles AS role WHERE oid=%s", (oid,))
            assert cursor.fetchone()[0] == before_role
            cursor.execute(
                "SELECT to_jsonb(membership) FROM pg_auth_members AS membership WHERE member=%s ORDER BY roleid,grantor",
                (oid,),
            )
            assert cursor.fetchall() == before_memberships
    finally:
        try:
            _drop_logins(url, created_logins, created_memberships)
        finally:
            try:
                if sentinel is not None:
                    if not drop_owned_role(connection, sentinel):
                        raise DisposableTargetError("outer collision fixture identity changed")
            finally:
                connection.close()
