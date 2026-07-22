"""Check hosted PostgreSQL authorization without disclosing live topology."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from functools import partial
from typing import Any, NamedTuple
from urllib.parse import SplitResult, urlsplit

SUCCESS = 0
CHECK_FAILED = 1
USAGE_ERROR = 2

SUPPORTED_DATABASE_URL_ENVS = (
    "DATABASE_URL",
    "ASSET_GRAPH_DATABASE_URL",
    "COORDINATION_DATABASE_URL",
    "POSTGRES_URL",
)
UNTRUSTED_DATABASE_ROLES_ENV = "FARDB_UNTRUSTED_DATABASE_ROLES"
EXPOSED_DATABASE_SCHEMAS_ENV = "FARDB_EXPOSED_DATABASE_SCHEMAS"
DEFAULT_UNTRUSTED_DATABASE_ROLES = ("anon", "authenticated")
SAFE_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
SAFE_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
CONNECT_TIMEOUT_SECONDS = 10
STATEMENT_TIMEOUT_MILLISECONDS = 15_000
LOCK_TIMEOUT_MILLISECONDS = 5_000

AUTHORIZATION_POSTURE_QUERY = """
WITH untrusted_roles AS (
    SELECT oid
    FROM pg_roles
    WHERE rolname = ANY(%(untrusted_roles)s)
),
role_posture AS (
    SELECT COUNT(*)::INTEGER AS resolved_untrusted_role_count
    FROM untrusted_roles
),
schema_namespace AS (
    SELECT oid
    FROM pg_namespace
    WHERE nspname = %(schema)s
),
exposed_tables AS (
    SELECT c.oid, c.relrowsecurity
    FROM pg_class AS c
    JOIN schema_namespace AS sn ON sn.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
),
table_posture AS (
    SELECT
        COUNT(*)::INTEGER AS table_count,
        COUNT(*) FILTER (WHERE relrowsecurity)::INTEGER AS rls_enabled_count,
        COUNT(*) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM untrusted_roles AS ur
                WHERE has_table_privilege(
                    ur.oid,
                    et.oid,
                    'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
                )
                    OR has_any_column_privilege(
                        ur.oid,
                        et.oid,
                        'SELECT, INSERT, UPDATE, REFERENCES'
                    )
            )
        )::INTEGER AS untrusted_grant_table_count
    FROM exposed_tables AS et
),
sequence_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_sequence_count
    FROM pg_class AS c
    JOIN schema_namespace AS sn ON sn.oid = c.relnamespace
    WHERE c.relkind = 'S'
        AND EXISTS (
            SELECT 1
            FROM untrusted_roles AS ur
            WHERE has_sequence_privilege(ur.oid, c.oid, 'USAGE, SELECT, UPDATE')
        )
),
function_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_function_count
    FROM pg_proc AS p
    JOIN schema_namespace AS sn ON sn.oid = p.pronamespace
    WHERE EXISTS (
        SELECT 1
        FROM untrusted_roles AS ur
        WHERE has_function_privilege(ur.oid, p.oid, 'EXECUTE')
    )
),
view_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_view_count
    FROM pg_class AS c
    JOIN schema_namespace AS sn ON sn.oid = c.relnamespace
    WHERE c.relkind IN ('v', 'm')
        AND EXISTS (
            SELECT 1
            FROM untrusted_roles AS ur
            WHERE has_table_privilege(
                ur.oid,
                c.oid,
                'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
            )
                OR has_any_column_privilege(
                    ur.oid,
                    c.oid,
                    'SELECT, INSERT, UPDATE, REFERENCES'
                )
        )
),
policy_posture AS (
    SELECT COUNT(*)::INTEGER AS unsafe_policy_count
    FROM pg_policies
    WHERE schemaname = %(schema)s
        AND (
            COALESCE(qual, '') ILIKE '%%user_metadata%%'
            OR COALESCE(with_check, '') ILIKE '%%user_metadata%%'
            OR COALESCE(qual, '') ILIKE '%%auth.role%%'
            OR COALESCE(with_check, '') ILIKE '%%auth.role%%'
        )
)
SELECT
    table_posture.table_count,
    table_posture.rls_enabled_count,
    table_posture.untrusted_grant_table_count,
    sequence_posture.untrusted_sequence_count,
    function_posture.untrusted_function_count,
    view_posture.untrusted_view_count,
    policy_posture.unsafe_policy_count,
    role_posture.resolved_untrusted_role_count
FROM schema_namespace
CROSS JOIN role_posture
CROSS JOIN table_posture
CROSS JOIN sequence_posture
CROSS JOIN function_posture
CROSS JOIN view_posture
CROSS JOIN policy_posture
"""


class AuthorizationSnapshot(NamedTuple):
    """Aggregate authorization evidence that contains no object identifiers."""

    table_count: int
    rls_enabled_count: int
    untrusted_grant_table_count: int
    untrusted_sequence_count: int
    untrusted_function_count: int
    untrusted_view_count: int
    unsafe_policy_count: int
    resolved_untrusted_role_count: int


class Finding(NamedTuple):
    """A bounded control failure safe for operator and CI output."""

    control: str
    message: str


class TrustedDatabaseUrl(str):
    """A PostgreSQL URL accepted from the fixed deployment configuration boundary."""


CONTROL_MESSAGES = {
    "authorization-evidence-integrity": "authorization evidence was internally inconsistent",
    "exposed-schema-rls": "one or more exposed-schema tables do not have row-level security enabled",
    "untrusted-table-access": "an untrusted provider role retains table data authority",
    "untrusted-sequence-access": "an untrusted provider role retains sequence authority",
    "untrusted-function-access": "an exposed function is executable by an untrusted role",
    "untrusted-view-access": "an untrusted provider role retains view access",
    "policy-claim-safety": "an authorization policy uses an unsafe or deprecated claim pattern",
}


def _snapshot_from_mapping(row: Mapping[str, Any]) -> AuthorizationSnapshot:
    """Build an authorization snapshot from one aggregate query row."""
    return AuthorizationSnapshot(
        table_count=int(row["table_count"]),
        rls_enabled_count=int(row["rls_enabled_count"]),
        untrusted_grant_table_count=int(row["untrusted_grant_table_count"]),
        untrusted_sequence_count=int(row["untrusted_sequence_count"]),
        untrusted_function_count=int(row["untrusted_function_count"]),
        untrusted_view_count=int(row["untrusted_view_count"]),
        unsafe_policy_count=int(row["unsafe_policy_count"]),
        resolved_untrusted_role_count=int(row["resolved_untrusted_role_count"]),
    )


def _snapshot_is_consistent(snapshot: AuthorizationSnapshot) -> bool:
    """Return whether aggregate counts can represent a valid database posture."""
    values = tuple(snapshot)
    if any(value < 0 for value in values):
        return False
    return (
        snapshot.rls_enabled_count <= snapshot.table_count
        and snapshot.untrusted_grant_table_count <= snapshot.table_count
    )


def evaluate_snapshot(snapshot: AuthorizationSnapshot) -> list[Finding]:
    """Evaluate aggregate authorization evidence without exposing counts or names."""
    if not _snapshot_is_consistent(snapshot):
        return [Finding("authorization-evidence-integrity", CONTROL_MESSAGES["authorization-evidence-integrity"])]

    findings: list[Finding] = []
    checks = (
        (snapshot.table_count == 0 or snapshot.rls_enabled_count != snapshot.table_count, "exposed-schema-rls"),
        (snapshot.untrusted_grant_table_count != 0, "untrusted-table-access"),
        (snapshot.untrusted_sequence_count != 0, "untrusted-sequence-access"),
        (snapshot.untrusted_function_count != 0, "untrusted-function-access"),
        (snapshot.untrusted_view_count != 0, "untrusted-view-access"),
        (snapshot.unsafe_policy_count != 0, "policy-claim-safety"),
    )
    for failed, control in checks:
        if failed:
            findings.append(Finding(control, CONTROL_MESSAGES[control]))
    return findings


def _description_name(description: Any) -> str:
    """Return a DB-API cursor-description column name."""
    name = getattr(description, "name", None)
    if isinstance(name, str):
        return name
    return str(description[0])


def _query_snapshot_mapping(connection: Any, schema: str, untrusted_roles: Sequence[str]) -> Mapping[str, Any]:
    """Execute the aggregate posture query and return a named result mapping."""
    with connection.cursor() as cursor:
        cursor.execute(
            AUTHORIZATION_POSTURE_QUERY,
            {"schema": schema, "untrusted_roles": list(untrusted_roles)},
        )
        raw_row = cursor.fetchone()
        if raw_row is None or cursor.description is None:
            raise RuntimeError("authorization query returned no evidence")
        columns = [_description_name(item) for item in cursor.description]
    return dict(zip(columns, raw_row, strict=True))


def _validate_role_resolution(
    resolved_role_count: int,
    configured_untrusted_role_count: int,
    *,
    require_all_untrusted_roles: bool,
) -> None:
    """Reject inconsistent or incomplete role resolution evidence when required."""
    if resolved_role_count > configured_untrusted_role_count:
        raise RuntimeError("authorization query returned inconsistent role evidence")
    if require_all_untrusted_roles and resolved_role_count != configured_untrusted_role_count:
        raise RuntimeError("authorization query did not resolve configured roles")


def collect_snapshot(
    connection: Any,
    schema: str,
    untrusted_roles: Sequence[str] = DEFAULT_UNTRUSTED_DATABASE_ROLES,
    require_all_untrusted_roles: bool = False,
) -> AuthorizationSnapshot:
    """Collect one read-only aggregate authorization snapshot."""
    connection.set_session(readonly=True, autocommit=False)
    try:
        row = _query_snapshot_mapping(connection, schema, untrusted_roles)
        snapshot = _snapshot_from_mapping(row)
    finally:
        connection.rollback()

    _validate_role_resolution(
        snapshot.resolved_untrusted_role_count,
        len(untrusted_roles),
        require_all_untrusted_roles=require_all_untrusted_roles,
    )
    return snapshot


def _parse_database_url(database_url: str) -> SplitResult | None:
    """Parse a database URL and reject malformed port syntax."""
    try:
        parsed = urlsplit(database_url)
        _ = parsed.port
    except ValueError:
        return None
    return parsed


def _has_supported_database_scheme(parsed: SplitResult) -> bool:
    """Return whether the URL uses the PostgreSQL protocol."""
    return parsed.scheme in {"postgres", "postgresql"}


def _has_database_authority(parsed: SplitResult) -> bool:
    """Return whether hosted connection identity and destination fields are present."""
    return bool(parsed.hostname and parsed.username)


def _has_database_name(parsed: SplitResult) -> bool:
    """Return whether the URL selects a database."""
    return parsed.path not in {"", "/"}


def _has_safe_database_url_suffix(parsed: SplitResult) -> bool:
    """Return whether the URL avoids unsupported client-side fragments."""
    return not parsed.fragment


def _has_valid_database_port(parsed: SplitResult) -> bool:
    """Return whether an explicit PostgreSQL port is in the usable TCP range."""
    return parsed.port is None or 1 <= parsed.port <= 65535


def _validate_database_url(database_url: str) -> TrustedDatabaseUrl | None:
    """Return a trusted hosted PostgreSQL URL or fail closed without exposing it."""
    parsed = _parse_database_url(database_url)
    if parsed is None:
        return None

    validators = (
        _has_supported_database_scheme,
        _has_database_authority,
        _has_database_name,
        _has_safe_database_url_suffix,
        _has_valid_database_port,
    )
    if not all(validator(parsed) for validator in validators):
        return None
    return TrustedDatabaseUrl(database_url)


def _configured_database_urls(environment: Mapping[str, str]) -> tuple[TrustedDatabaseUrl, ...] | None:
    """Resolve and validate distinct URLs from the fixed deployment configuration allowlist."""
    configured: list[TrustedDatabaseUrl] = []
    for variable_name in SUPPORTED_DATABASE_URL_ENVS:
        raw_url = environment.get(variable_name)
        if not raw_url:
            continue
        database_url = _validate_database_url(raw_url)
        if database_url is None:
            return None
        if database_url not in configured:
            configured.append(database_url)
    return tuple(configured)


def _configured_untrusted_roles(environment: Mapping[str, str]) -> tuple[str, ...] | None:
    """Resolve untrusted provider-role identities without exposing them in output."""
    raw_roles = environment.get(UNTRUSTED_DATABASE_ROLES_ENV)
    if raw_roles is None:
        return DEFAULT_UNTRUSTED_DATABASE_ROLES

    roles = tuple(dict.fromkeys(role.strip() for role in raw_roles.split(",")))
    if not roles or any(not SAFE_ROLE_PATTERN.fullmatch(role) for role in roles):
        return None
    return roles


def _configured_exposed_schemas(
    environment: Mapping[str, str],
    cli_schema: str,
) -> tuple[str, ...] | None:
    """Resolve exposed schemas from env (comma-separated) or the CLI default.

    When ``FARDB_EXPOSED_DATABASE_SCHEMAS`` is set, every listed schema is checked
    so a promotion PASS cannot omit non-``public`` inventoried schemas. When unset,
    the ``--exposed-schema`` value is used (default ``public``).
    """
    raw_schemas = environment.get(EXPOSED_DATABASE_SCHEMAS_ENV)
    schemas: tuple[str, ...]
    if raw_schemas is None:
        schemas = (cli_schema,)
    else:
        schemas = tuple(dict.fromkeys(part.strip() for part in raw_schemas.split(",") if part.strip()))
        if not schemas:
            return None
    if any(not SAFE_SCHEMA_PATTERN.fullmatch(schema) for schema in schemas):
        return None
    return schemas


def _connect(database_url: TrustedDatabaseUrl) -> Any:
    """Open a bounded PostgreSQL connection without importing the driver during unit tests."""
    import psycopg2

    options = f"-c statement_timeout={STATEMENT_TIMEOUT_MILLISECONDS} " + f"-c lock_timeout={LOCK_TIMEOUT_MILLISECONDS}"
    return psycopg2.connect(
        database_url,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        application_name="fardb-authorization-check",
        options=options,
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exposed-schema",
        default="public",
        help="Exposed schema to check when FARDB_EXPOSED_DATABASE_SCHEMAS is unset (default: public).",
    )
    return parser.parse_args(argv)


def _print_findings(findings: Sequence[Finding]) -> None:
    """Print bounded control failures without topology or counts."""
    print("database authorization gate failed")
    for finding in findings:
        print(f"- {finding.control}: {finding.message}")


def _collect_configured_snapshots(
    database_urls: Sequence[TrustedDatabaseUrl],
    snapshot_collector: Callable[[Any], AuthorizationSnapshot],
    connector: Callable[[TrustedDatabaseUrl], Any],
) -> list[AuthorizationSnapshot] | None:
    """Collect all configured snapshots, treating connection and cleanup errors as one bounded failure."""
    snapshots: list[AuthorizationSnapshot] = []
    try:
        for database_url in database_urls:
            with closing(connector(database_url)) as connection:
                snapshots.append(snapshot_collector(connection))
    except Exception:
        return None
    return snapshots


def _evaluate_snapshots(snapshots: Sequence[AuthorizationSnapshot]) -> list[Finding]:
    """Combine control failures without revealing which configured boundary produced them."""
    findings_by_control: dict[str, Finding] = {}
    for snapshot in snapshots:
        for finding in evaluate_snapshot(snapshot):
            findings_by_control.setdefault(finding.control, finding)
    return list(findings_by_control.values())


class GateConfiguration(NamedTuple):
    """Resolved runtime inputs for one authorization-gate invocation."""

    database_urls: tuple[TrustedDatabaseUrl, ...]
    untrusted_roles: tuple[str, ...]
    exposed_schemas: tuple[str, ...]
    require_all_untrusted_roles: bool


def _reject_invalid_configuration() -> int:
    """Emit the bounded invalid-configuration message and return the usage exit code."""
    print("database authorization check configuration is invalid", file=sys.stderr)
    return USAGE_ERROR


def _resolve_gate_configuration(
    environ: Mapping[str, str],
    *,
    cli_exposed_schema: str,
) -> GateConfiguration | int:
    """Resolve gate inputs, or return a usage/config exit code when invalid."""
    if not SAFE_SCHEMA_PATTERN.fullmatch(cli_exposed_schema):
        return _reject_invalid_configuration()

    database_urls = _configured_database_urls(environ)
    if database_urls is None:
        return _reject_invalid_configuration()
    untrusted_roles = _configured_untrusted_roles(environ)
    if untrusted_roles is None:
        return _reject_invalid_configuration()
    exposed_schemas = _configured_exposed_schemas(environ, cli_exposed_schema)
    if exposed_schemas is None:
        return _reject_invalid_configuration()
    if not database_urls:
        print("database authorization check requires a configured database URL", file=sys.stderr)
        return USAGE_ERROR

    return GateConfiguration(
        database_urls=database_urls,
        untrusted_roles=untrusted_roles,
        exposed_schemas=exposed_schemas,
        require_all_untrusted_roles=UNTRUSTED_DATABASE_ROLES_ENV in environ,
    )


def _collect_snapshots_for_schemas(
    configuration: GateConfiguration,
    connect: Callable[[TrustedDatabaseUrl], Any],
) -> list[AuthorizationSnapshot] | None:
    """Collect snapshots for every exposed schema, or None when any boundary fails."""
    snapshots: list[AuthorizationSnapshot] = []
    for schema in configuration.exposed_schemas:
        snapshot_collector = partial(
            collect_snapshot,
            schema=schema,
            untrusted_roles=configuration.untrusted_roles,
            require_all_untrusted_roles=configuration.require_all_untrusted_roles,
        )
        schema_snapshots = _collect_configured_snapshots(
            configuration.database_urls,
            snapshot_collector,
            connect,
        )
        if schema_snapshots is None:
            return None
        snapshots.extend(schema_snapshots)
    return snapshots


def main(
    argv: Sequence[str] | None = None,
    *,
    connector: Callable[[TrustedDatabaseUrl], Any] | None = None,
) -> int:
    """Run the database authorization gate."""
    args = _parse_args(argv)
    configuration = _resolve_gate_configuration(
        os.environ,
        cli_exposed_schema=args.exposed_schema,
    )
    if isinstance(configuration, int):
        return configuration

    snapshots = _collect_snapshots_for_schemas(configuration, connector or _connect)
    if snapshots is None:
        print("database authorization check could not complete", file=sys.stderr)
        return CHECK_FAILED

    findings = _evaluate_snapshots(snapshots)
    if findings:
        _print_findings(findings)
        return CHECK_FAILED

    print("database authorization gate passed")
    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
