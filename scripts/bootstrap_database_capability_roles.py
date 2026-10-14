"""Orchestrate identity-checked, multi-database capability-role bootstrap."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extensions import make_dsn

_ROLE_NAMES = (
    "fardb_runtime_auth",
    "fardb_runtime_graph",
    "fardb_runtime_coordination",
)
_BOOTSTRAP_SQL = Path(__file__).with_name("bootstrap_database_capability_roles.sql")
_CONNECT_TIMEOUT_SECONDS = 10
_LOCK_TIMEOUT = "5s"
_STATEMENT_TIMEOUT = "30s"


class BootstrapTargetError(RuntimeError):
    """A mapped database could not be identified or safely checked."""


class BootstrapOutcomeIndeterminate(RuntimeError):
    """The coordinator connection failed while commit outcome was unknown."""


def _normalize_mapping(cursor, mapping: Mapping[str, object] | None) -> dict[str, list[str]]:
    """Validate the complete fixed-role mapping before opening target sessions."""
    if not isinstance(mapping, Mapping) or set(mapping) != set(_ROLE_NAMES):
        raise BootstrapTargetError("complete FarDB bootstrap target mapping is required")
    normalized: dict[str, list[str]] = {}
    for role in _ROLE_NAMES:
        targets = mapping[role]
        if not isinstance(targets, (list, tuple)) or not targets:
            raise BootstrapTargetError(f"invalid FarDB bootstrap target list: {role}")
        if any(not isinstance(database, str) or not database for database in targets):
            raise BootstrapTargetError(f"invalid FarDB bootstrap target database: {role}")
        normalized[role] = list(dict.fromkeys(targets))
    return normalized


def _cluster_and_database_identity(connection: PsycopgConnection) -> tuple[str, int, str]:
    """Read cluster lineage and the connected database identity on one session."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT control.system_identifier::text, database.oid::bigint, database.datname "
            "FROM pg_catalog.pg_control_system() AS control "
            "JOIN pg_catalog.pg_database AS database "
            "ON database.datname = pg_catalog.current_database()"
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise BootstrapTargetError("mapped database identity is unavailable or ambiguous")
    system_identifier, database_oid, database_name = rows[0]
    if (
        not isinstance(system_identifier, str)
        or not system_identifier.isascii()
        or not system_identifier.isdecimal()
        or int(system_identifier) <= 0
        or not isinstance(database_oid, int)
        or database_oid <= 0
        or not isinstance(database_name, str)
        or not database_name
    ):
        raise BootstrapTargetError("mapped database identity is invalid")
    return system_identifier, database_oid, database_name


def _coordinator_targets(cursor, mapping: dict[str, list[str]]) -> dict[str, tuple[int, str]]:
    """Resolve every explicit database name from the locked shared catalog."""
    requested = sorted({database for databases in mapping.values() for database in databases})
    cursor.execute(
        "SELECT oid::bigint, datname FROM pg_catalog.pg_database WHERE datname = ANY(%s) ORDER BY oid",
        (requested,),
    )
    rows = cursor.fetchall()
    identities = {name: (int(oid), name) for oid, name in rows}
    if set(identities) != set(requested):
        raise BootstrapTargetError("invalid FarDB bootstrap target database")
    return identities


def _lock_coordinator_catalogs(cursor) -> None:
    """Protect shared role and database state while allowing this transaction to write."""
    cursor.execute("SET LOCAL lock_timeout = %s", (_LOCK_TIMEOUT,))
    cursor.execute("SET LOCAL statement_timeout = %s", (_STATEMENT_TIMEOUT,))
    for catalog in ("pg_authid", "pg_auth_members", "pg_database"):
        cursor.execute(f"LOCK TABLE pg_catalog.{catalog} IN SHARE ROW EXCLUSIVE MODE")


def _require_superuser(cursor) -> None:
    """Preserve the bootstrap SQL's explicit rejection before privileged catalog locks."""
    cursor.execute("SELECT COALESCE((SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = CURRENT_USER), FALSE)")
    if not cursor.fetchone()[0]:
        raise psycopg2.Error("FarDB capability-role bootstrap requires a PostgreSQL superuser")


def _lock_target_schema_catalog(connection: PsycopgConnection) -> None:
    """Prevent concurrent schema ACL changes in one target database."""
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = %s", (_LOCK_TIMEOUT,))
        cursor.execute("SET LOCAL statement_timeout = %s", (_STATEMENT_TIMEOUT,))
        cursor.execute("LOCK TABLE pg_catalog.pg_namespace IN SHARE MODE")


def _schema_create_is_effective(connection: PsycopgConnection, capability_oid: int) -> bool:
    """Check an existing role's effective CREATE privilege in this database."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace AS namespace "
            "WHERE pg_catalog.has_schema_privilege(%s, namespace.oid, 'CREATE'))",
            (capability_oid,),
        )
        return bool(cursor.fetchone()[0])


def _public_schema_create_exists(connection: PsycopgConnection) -> bool:
    """Inspect actual PUBLIC schema ACLs for a role that bootstrap will create."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_namespace AS namespace "
            "CROSS JOIN LATERAL pg_catalog.aclexplode("
            "COALESCE(namespace.nspacl, pg_catalog.acldefault('n', namespace.nspowner))"
            ") AS acl "
            "WHERE acl.grantee = 0 AND acl.privilege_type = 'CREATE')"
        )
        return bool(cursor.fetchone()[0])


def _capability_oids(cursor) -> dict[str, int | None]:
    """Snapshot the committed capability role OIDs before bootstrap mutations."""
    cursor.execute(
        "SELECT rolname, oid::bigint FROM pg_catalog.pg_roles WHERE rolname = ANY(%s)",
        (list(_ROLE_NAMES),),
    )
    roles: dict[str, int | None] = dict.fromkeys(_ROLE_NAMES)
    roles.update({role: int(oid) for role, oid in cursor.fetchall()})
    return roles


def _verify_target_schema_acl(
    connection: PsycopgConnection,
    mapping: dict[str, list[str]],
    database_name: str,
    role_oids: dict[str, int | None],
) -> None:
    """Reject CREATE authority using only this target's own schema catalog."""
    for role, databases in mapping.items():
        if database_name not in databases:
            continue
        role_oid = role_oids[role]
        has_create = (
            _schema_create_is_effective(connection, role_oid)
            if role_oid is not None
            else _public_schema_create_exists(connection)
        )
        if has_create:
            raise BootstrapTargetError(f"unsafe FarDB capability schema CREATE privilege: {role}")


def _visible_target_role_oids(
    connection: PsycopgConnection, coordinator_oids: dict[str, int | None]
) -> dict[str, int | None]:
    """Resolve committed role identities without assuming visibility of coordinator writes."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolname, oid::bigint FROM pg_catalog.pg_roles WHERE rolname = ANY(%s)",
            (list(_ROLE_NAMES),),
        )
        target_oids = {role: int(oid) for role, oid in cursor.fetchall()}
    visible: dict[str, int | None] = {}
    for role in _ROLE_NAMES:
        coordinator_oid = coordinator_oids[role]
        target_oid = target_oids.get(role)
        if coordinator_oid is None and target_oid is not None:
            raise BootstrapTargetError("capability role identity differs between mapped database sessions")
        if coordinator_oid is not None and target_oid is not None and coordinator_oid != target_oid:
            raise BootstrapTargetError("capability role identity differs between mapped database sessions")
        # A coordinator-only role was created earlier in its still-uncommitted
        # transaction. Treat it as a new role and inspect only real PUBLIC ACLs.
        visible[role] = target_oid
    return visible


def _open_target_connections(
    coordinator: PsycopgConnection,
    target_database_url: str | None,
    target_identities: dict[str, tuple[int, str]],
    coordinator_identity: tuple[str, int, str],
    stack: ExitStack,
) -> dict[str, PsycopgConnection]:
    """Open and prove each distinct database using the coordinator's libpq route."""
    connections: dict[str, PsycopgConnection] = {}
    for database_name, (expected_oid, expected_name) in sorted(
        target_identities.items(), key=lambda item: (item[1][0], item[1][1])
    ):
        if database_name == coordinator_identity[2]:
            target_connection = coordinator
        else:
            if not target_database_url:
                raise BootstrapTargetError(
                    "a protected target connection URL is required for mapped secondary databases"
                )
            dsn = make_dsn(
                target_database_url,
                dbname=database_name,
                connect_timeout=_CONNECT_TIMEOUT_SECONDS,
                application_name="fardb-capability-bootstrap-target",
            )
            target_connection = psycopg2.connect(dsn)
            stack.callback(target_connection.close)
        observed = _cluster_and_database_identity(target_connection)
        if observed != (coordinator_identity[0], expected_oid, expected_name):
            raise BootstrapTargetError("mapped database does not match the identity-proved cluster target")
        connections[database_name] = target_connection
    return connections


def _preflight_targets(
    cursor,
    connection: PsycopgConnection,
    target_database_url: str | None,
    mapping: dict[str, list[str]],
    target_identities: dict[str, tuple[int, str]],
    coordinator_identity: tuple[str, int, str],
    stack: ExitStack,
) -> tuple[dict[str, PsycopgConnection], dict[str, dict[str, int | None]]]:
    """Lock every local namespace and prove schema ACLs before role mutation."""
    target_connections = _open_target_connections(
        connection, target_database_url, target_identities, coordinator_identity, stack
    )
    role_oids = _capability_oids(cursor)
    target_role_oids: dict[str, dict[str, int | None]] = {}
    for database_name, target_connection in sorted(
        target_connections.items(), key=lambda item: (target_identities[item[0]][0], item[0])
    ):
        _lock_target_schema_catalog(target_connection)
        visible_oids = _visible_target_role_oids(target_connection, role_oids)
        target_role_oids[database_name] = visible_oids
        _verify_target_schema_acl(target_connection, mapping, database_name, visible_oids)
    return target_connections, target_role_oids


def _apply_bootstrap(cursor, mapping: dict[str, list[str]]) -> None:
    """Keep complete mapping configuration and the reviewed SQL in one transaction."""
    cursor.execute(
        "SELECT pg_catalog.set_config('fardb.bootstrap_targets', %s, true)",
        (json.dumps(mapping, sort_keys=True, separators=(",", ":")),),
    )
    cursor.execute(_BOOTSTRAP_SQL.read_text(encoding="utf-8"))


def _prepare_and_apply_bootstrap(
    cursor,
    connection: PsycopgConnection,
    mapping: Mapping[str, object] | None,
    target_database_url: str | None,
    stack: ExitStack,
) -> dict[str, PsycopgConnection]:
    """Preflight all targets, apply fixed reviewed SQL, and recheck locked ACLs."""
    _require_superuser(cursor)
    _lock_coordinator_catalogs(cursor)
    normalized = _normalize_mapping(cursor, mapping)
    coordinator_identity = _cluster_and_database_identity(connection)
    target_identities = _coordinator_targets(cursor, normalized)
    target_connections, target_role_oids = _preflight_targets(
        cursor,
        connection,
        target_database_url,
        normalized,
        target_identities,
        coordinator_identity,
        stack,
    )
    _apply_bootstrap(cursor, normalized)
    _verify_locked_target_state(
        target_connections,
        target_role_oids,
        normalized,
        target_identities,
        coordinator_identity,
    )
    return target_connections


def _verify_locked_target_state(
    target_connections: dict[str, PsycopgConnection],
    target_role_oids: dict[str, dict[str, int | None]],
    mapping: dict[str, list[str]],
    target_identities: dict[str, tuple[int, str]],
    coordinator_identity: tuple[str, int, str],
) -> None:
    """Recheck stable identity and ACL facts without relying on uncommitted role visibility."""
    for database_name, target_connection in target_connections.items():
        observed = _cluster_and_database_identity(target_connection)
        expected_oid, expected_name = target_identities[database_name]
        if observed != (coordinator_identity[0], expected_oid, expected_name):
            raise BootstrapTargetError("mapped database identity changed during bootstrap")
        _verify_target_schema_acl(target_connection, mapping, database_name, target_role_oids[database_name])


def _release_target_transactions(
    target_connections: dict[str, PsycopgConnection], coordinator: PsycopgConnection
) -> None:
    """Release read-only target locks; close a target if its rollback fails."""
    for target_connection in target_connections.values():
        if target_connection is not coordinator and not target_connection.closed:
            try:
                target_connection.rollback()
            except Exception:
                target_connection.close()


def bootstrap_capability_roles(
    cursor,
    mapping: Mapping[str, object] | None = None,
    *,
    target_database_url: str | None = None,
) -> None:
    """Bootstrap roles atomically after identity-proved checks in every mapped database."""
    connection: PsycopgConnection = cursor.connection
    began_explicitly = bool(connection.autocommit)
    transaction_started = False
    commit_started = False
    target_connections: dict[str, PsycopgConnection] = {}
    with ExitStack() as stack:
        try:
            mapping = _normalize_mapping(cursor, mapping)
            if began_explicitly:
                cursor.execute("BEGIN")
                transaction_started = True
            target_connections = _prepare_and_apply_bootstrap(cursor, connection, mapping, target_database_url, stack)
            commit_started = True
            if began_explicitly:
                cursor.execute("COMMIT")
            else:
                connection.commit()
        except BootstrapOutcomeIndeterminate:
            raise
        except BaseException as exc:
            if commit_started:
                raise BootstrapOutcomeIndeterminate(
                    "bootstrap commit outcome is indeterminate; do not retry without operator verification"
                ) from exc
            if began_explicitly:
                if transaction_started:
                    cursor.execute("ROLLBACK")
            else:
                connection.rollback()
            raise
        finally:
            _release_target_transactions(target_connections, connection)


def main(argv: list[str] | None = None) -> int:
    """Run the explicit operator entrypoint without placing credentials in arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets-json", required=True, help="complete fixed-role to database-name mapping")
    arguments = parser.parse_args(argv)
    database_url = os.environ.get("FARDB_BOOTSTRAP_DATABASE_URL")
    if not database_url:
        parser.error("FARDB_BOOTSTRAP_DATABASE_URL must be provided through the protected operator environment")
    mapping = _normalize_mapping(None, json.loads(arguments.targets_json))
    with (
        psycopg2.connect(database_url, connect_timeout=_CONNECT_TIMEOUT_SECONDS) as connection,
        connection.cursor() as cursor,
    ):
        bootstrap_capability_roles(cursor, mapping, target_database_url=database_url)
    print("FarDB capability-role bootstrap accepted for every identity-proved target")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
