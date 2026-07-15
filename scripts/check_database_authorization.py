"""Check hosted PostgreSQL authorization without disclosing live topology."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

SUCCESS = 0
CHECK_FAILED = 1
USAGE_ERROR = 2

SUPPORTED_DATABASE_URL_ENVS = (
    "DATABASE_URL",
    "ASSET_GRAPH_DATABASE_URL",
    "COORDINATION_DATABASE_URL",
    "POSTGRES_URL",
)
SAFE_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

AUTHORIZATION_POSTURE_QUERY = """
WITH schema_namespace AS (
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
            WHERE has_table_privilege('anon', oid, 'SELECT')
               OR has_table_privilege('anon', oid, 'INSERT')
               OR has_table_privilege('anon', oid, 'UPDATE')
               OR has_table_privilege('anon', oid, 'DELETE')
               OR has_table_privilege('authenticated', oid, 'SELECT')
               OR has_table_privilege('authenticated', oid, 'INSERT')
               OR has_table_privilege('authenticated', oid, 'UPDATE')
               OR has_table_privilege('authenticated', oid, 'DELETE')
        )::INTEGER AS untrusted_grant_table_count
    FROM exposed_tables
),
sequence_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_sequence_count
    FROM pg_class AS c
    JOIN schema_namespace AS sn ON sn.oid = c.relnamespace
    WHERE c.relkind = 'S'
      AND (
          has_sequence_privilege('anon', c.oid, 'USAGE')
          OR has_sequence_privilege('anon', c.oid, 'SELECT')
          OR has_sequence_privilege('anon', c.oid, 'UPDATE')
          OR has_sequence_privilege('authenticated', c.oid, 'USAGE')
          OR has_sequence_privilege('authenticated', c.oid, 'SELECT')
          OR has_sequence_privilege('authenticated', c.oid, 'UPDATE')
      )
),
function_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_function_count
    FROM pg_proc AS p
    JOIN schema_namespace AS sn ON sn.oid = p.pronamespace
    WHERE (
          has_function_privilege('anon', p.oid, 'EXECUTE')
          OR has_function_privilege('authenticated', p.oid, 'EXECUTE')
      )
),
view_posture AS (
    SELECT COUNT(*)::INTEGER AS untrusted_view_count
    FROM pg_class AS c
    JOIN schema_namespace AS sn ON sn.oid = c.relnamespace
    WHERE c.relkind IN ('v', 'm')
      AND (
          has_table_privilege('anon', c.oid, 'SELECT')
          OR has_table_privilege('authenticated', c.oid, 'SELECT')
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
    policy_posture.unsafe_policy_count
FROM schema_namespace
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


class Finding(NamedTuple):
    """A bounded control failure safe for operator and CI output."""

    control: str
    message: str


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
        (snapshot.rls_enabled_count != snapshot.table_count, "exposed-schema-rls"),
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


def collect_snapshot(connection: Any, schema: str) -> AuthorizationSnapshot:
    """Collect one read-only aggregate authorization snapshot."""
    connection.set_session(readonly=True, autocommit=False)
    with connection.cursor() as cursor:
        cursor.execute(AUTHORIZATION_POSTURE_QUERY, {"schema": schema})
        raw_row = cursor.fetchone()
        if raw_row is None or cursor.description is None:
            raise RuntimeError("authorization query returned no evidence")
        columns = [_description_name(item) for item in cursor.description]
        row = dict(zip(columns, raw_row, strict=True))
    connection.rollback()
    return _snapshot_from_mapping(row)


def _connect(database_url: str) -> Any:
    """Open a bounded PostgreSQL connection without importing the driver during unit tests."""
    import psycopg2

    return psycopg2.connect(database_url, connect_timeout=10, application_name="fardb-authorization-check")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url-env",
        choices=SUPPORTED_DATABASE_URL_ENVS,
        default="DATABASE_URL",
        help="Environment variable containing the PostgreSQL connection string.",
    )
    parser.add_argument(
        "--exposed-schema",
        default="public",
        help="Exposed schema to check (default: public).",
    )
    return parser.parse_args(argv)


def _print_findings(findings: Sequence[Finding]) -> None:
    """Print bounded control failures without topology or counts."""
    print("database authorization gate failed")
    for finding in findings:
        print(f"- {finding.control}: {finding.message}")


def main(
    argv: Sequence[str] | None = None,
    *,
    connector: Callable[[str], Any] | None = None,
) -> int:
    """Run the database authorization gate."""
    args = _parse_args(argv)
    if not SAFE_SCHEMA_PATTERN.fullmatch(args.exposed_schema):
        print("database authorization check configuration is invalid", file=sys.stderr)
        return USAGE_ERROR

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        print("database authorization check requires a configured database URL", file=sys.stderr)
        return USAGE_ERROR

    connect = connector or _connect
    connection = None
    snapshot = None
    check_failed = False
    try:
        connection = connect(database_url)
        snapshot = collect_snapshot(connection, args.exposed_schema)
    except Exception:
        check_failed = True
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                check_failed = True

    if check_failed or snapshot is None:
        print("database authorization check could not complete", file=sys.stderr)
        return CHECK_FAILED

    findings = evaluate_snapshot(snapshot)
    if findings:
        _print_findings(findings)
        return CHECK_FAILED

    print("database authorization gate passed")
    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
