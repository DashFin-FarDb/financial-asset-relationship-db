"""Dialect-aware GRAC v1 assertion schema helpers.

SQLite retains local additive setup and idempotent immutability guards.
PostgreSQL mutation belongs exclusively to the profile-scoped ledger; this
module verifies its constraints, triggers, grants, and policies read-only.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine, make_url

from src.data.check_constraint_normalization import normalize_check_definition
from src.data.relationship_assertion_db_models import (
    EFFECTIVE_WINDOW_CHECK,
    GRAC_TABLE_NAMES,
    STRENGTH_DECIMAL_CHECK,
)

# Keep names well under PostgreSQL's 63-byte identifier limit for every table.
_IMMUTABILITY_FUNCTION = "grac_v1_reject_mutation"
_TRIGGER_PREFIX = "grac_imm"
_GRAC_TABLE_NAME_SET = frozenset(GRAC_TABLE_NAMES)
# Match scripts/check_database_authorization.py untrusted-role resolution.
_UNTRUSTED_DATABASE_ROLES_ENV = "FARDB_UNTRUSTED_DATABASE_ROLES"
_DEFAULT_UNTRUSTED_DATABASE_ROLES = ("anon", "authenticated")
_SAFE_ROLE_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


def ensure_relationship_assertion_schema(engine: Engine) -> None:
    """
    Ensure local SQLite guards, while rejecting PostgreSQL schema mutation.

    SQLite tables are created by ``Base.metadata.create_all`` before this helper
    installs or repairs local guards. PostgreSQL callers fail closed and must use
    :func:`verify_relationship_assertion_schema` for read-only verification.
    """
    backend = make_url(str(engine.url)).get_backend_name()
    if backend == "postgresql":
        from src.data.database import SchemaCompatibilityError  # pylint: disable=import-outside-toplevel

        raise SchemaCompatibilityError("PostgreSQL GRAC schema mutation is owned by the profile-scoped Supabase ledger")
    with engine.begin() as connection:
        if backend == "sqlite":
            _ensure_projection_revision_scope_metadata(connection)
            _require_sqlite_grac_constraints(connection)
            if not _sqlite_guards_present(connection):
                _install_sqlite_immutability_guards(connection)


def verify_relationship_assertion_schema(engine: Engine) -> None:
    """Verify GRAC schema and authority invariants without performing repair."""
    backend = make_url(str(engine.url)).get_backend_name()
    with engine.connect() as connection:
        _require_projection_revision_scope_metadata(connection, backend)
        if backend == "sqlite":
            _verify_sqlite_grac_schema(connection)
        elif backend == "postgresql":
            _verify_postgresql_grac_schema(connection)


def _verify_sqlite_grac_schema(connection: Connection) -> None:
    """Verify SQLite GRAC compatibility and immutability guards."""
    _require_sqlite_grac_constraints(connection)
    if not _sqlite_guards_present(connection):
        raise RuntimeError("SQLite GRAC immutability guards are incomplete")


def _verify_postgresql_grac_schema(connection: Connection) -> None:
    """Verify PostgreSQL GRAC compatibility, guards, and least authority."""
    if not _postgresql_grac_constraints_present(connection):
        raise RuntimeError("PostgreSQL GRAC constraints are incomplete or unvalidated")
    if not _postgresql_guards_present(connection):
        raise RuntimeError("PostgreSQL GRAC immutability guards are incomplete")
    roles = _untrusted_database_roles()
    if _immutability_function_has_untrusted_execute(connection, roles):
        raise PermissionError("PostgreSQL GRAC immutability function is executable by an untrusted role")
    if not _postgresql_grac_access_hardened(connection):
        raise PermissionError("PostgreSQL GRAC RLS/grant posture is incompatible")


def _projection_revision_scope_metadata(connection: Connection, backend: str) -> tuple[set[str], set[str]]:
    """Read projection columns and assertion-event indexes for one backend."""
    if backend == "sqlite":
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(relationship_projection_revisions)"))}
        indexes = {row[1] for row in connection.execute(text("PRAGMA index_list(relationship_assertion_events)"))}
        return columns, indexes
    if backend != "postgresql":
        raise RuntimeError(f"unsupported database backend for GRAC verification: {backend}")

    columns = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'relationship_projection_revisions'"
            )
        )
    }
    indexes = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
                "AND tablename = 'relationship_assertion_events'"
            )
        )
    }
    return columns, indexes


def _require_projection_revision_scope_metadata(connection: Connection, backend: str) -> None:
    """Require the additive projection column and successor lookup index."""
    columns, indexes = _projection_revision_scope_metadata(connection, backend)

    if "governed_scopes" not in columns:
        raise RuntimeError("relationship_projection_revisions.governed_scopes is missing")
    required_index = "ix_relationship_assertion_events_successor_assertion_id"
    if required_index not in indexes:
        raise RuntimeError(f"{required_index} is missing")


def _ensure_projection_revision_scope_metadata(connection: Connection) -> None:
    """Add durable SQLite scope metadata and the successor FK index on upgrade."""
    requires_backfill = False
    rows = connection.execute(text("PRAGMA table_info(relationship_projection_revisions)")).fetchall()
    column_names = {row[1] for row in rows}
    if "governed_scopes" not in column_names:
        requires_backfill = True
        connection.execute(
            text("ALTER TABLE relationship_projection_revisions ADD COLUMN governed_scopes TEXT NOT NULL DEFAULT '[]'")
        )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_relationship_assertion_events_successor_assertion_id "
            "ON relationship_assertion_events (successor_assertion_id)"
        )
    )
    if requires_backfill:
        _backfill_projection_revision_scopes(connection)


def _backfill_projection_revision_scopes(connection: Connection) -> None:
    """Derive canonical metadata for revisions created before governed_scopes existed."""
    rows = connection.execute(
        text(
            "SELECT revision.id, revision.purpose, assertion.predicate_id "
            "FROM relationship_projection_revisions AS revision "
            "LEFT JOIN relationship_projection_edges AS edge ON edge.revision_id = revision.id "
            "LEFT JOIN relationship_assertions AS assertion ON assertion.id = edge.assertion_id "
            "ORDER BY revision.id, assertion.predicate_id"
        )
    ).all()
    scope_pairs: dict[str, tuple[str, set[str]]] = {}
    for revision_id, purpose, predicate_id in rows:
        existing_purpose, predicates = scope_pairs.setdefault(revision_id, (purpose, set()))
        if existing_purpose != purpose:
            raise RuntimeError(f"inconsistent purpose while backfilling revision {revision_id}")
        if predicate_id is not None:
            predicates.add(predicate_id)
    published_rows = connection.execute(
        text(
            "SELECT revision.id, revision.purpose "
            "FROM relationship_projection_revisions AS revision "
            "JOIN relationship_projection_publications AS publication "
            "ON publication.revision_id = revision.id "
            "JOIN rebuild_jobs AS job ON job.job_id = publication.rebuild_job_id "
            "WHERE job.status = 'succeeded' "
            "ORDER BY revision.purpose, publication.published_at, "
            "publication.rebuild_job_id, publication.id"
        )
    ).all()
    published_scopes: dict[str, set[str]] = {}
    for revision_id, purpose in published_rows:
        _revision_purpose, predicates = scope_pairs[revision_id]
        if predicates:
            published_scopes[purpose] = predicates
        elif prior := published_scopes.get(purpose):
            scope_pairs[revision_id] = (purpose, set(prior))
    payloads = [
        {
            "revision_id": revision_id,
            "governed_scopes": json.dumps(
                [{"predicate_id": predicate_id, "purpose": purpose} for predicate_id in sorted(predicates)],
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        for revision_id, (purpose, predicates) in scope_pairs.items()
    ]
    if not payloads:
        return
    _allow_projection_revision_backfill(connection)
    try:
        connection.execute(
            text(
                "UPDATE relationship_projection_revisions "
                "SET governed_scopes = :governed_scopes WHERE id = :revision_id"
            ),
            payloads,
        )
    finally:
        _restore_projection_revision_immutability(connection)


def _allow_projection_revision_backfill(connection: Connection) -> None:
    """Temporarily remove the SQLite revision update guard for backfill."""
    update_name, _delete_name, _truncate_name = list_immutability_trigger_names("relationship_projection_revisions")
    connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name}"))


def _restore_projection_revision_immutability(connection: Connection) -> None:
    """Restore the SQLite revision immutability guard after controlled backfill."""
    _install_sqlite_immutability_guards(connection)


def _require_sqlite_grac_constraints(connection: Connection) -> None:
    """Fail closed when a legacy SQLite database lacks non-additive GRAC CHECKs."""
    expected = {
        "relationship_assertions": "ck_relationship_assertions_effective_window",
        "relationship_projection_edges": "ck_relationship_projection_edges_strength",
    }
    rows = connection.execute(
        text("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name IN :tables").bindparams(
            bindparam("tables", expanding=True)
        ),
        {"tables": list(expected)},
    ).all()
    actual = {name: sql or "" for name, sql in rows}
    missing = [table for table, constraint in expected.items() if constraint not in actual.get(table, "")]
    if missing:
        raise RuntimeError(
            "legacy SQLite GRAC CHECK migration required for "
            + ", ".join(sorted(missing))
            + "; automatic table rebuild is intentionally not performed at application startup"
        )


def _postgresql_constraint_catalog(
    connection: Connection,
    names: list[str],
) -> dict[tuple[str, str], tuple[str, bool]]:
    """Return PostgreSQL CHECK definitions and validation state by table/name."""
    rows = connection.execute(
        text(
            "SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid), con.convalidated "
            "FROM pg_constraint AS con "
            "JOIN pg_class AS rel ON rel.oid = con.conrelid "
            "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
            "WHERE namespace.nspname = current_schema() AND con.conname IN :names"
        ).bindparams(bindparam("names", expanding=True)),
        {"names": names},
    ).all()
    return {(table, name): (definition, validated) for table, name, definition, validated in rows}


def _postgresql_check_matches(definition: str, canonical_check: str) -> bool:
    """Return whether a catalog CHECK matches the repository canonical predicate."""
    return normalize_check_definition(definition) == normalize_check_definition(canonical_check)


def _postgresql_grac_constraints_present(connection: Connection) -> bool:
    """Return whether the current schema has the validated GRAC compatibility checks."""
    expected = {
        ("relationship_assertions", "ck_relationship_assertions_effective_window"): EFFECTIVE_WINDOW_CHECK,
        ("relationship_projection_edges", "ck_relationship_projection_edges_strength"): STRENGTH_DECIMAL_CHECK,
    }
    actual = _postgresql_constraint_catalog(
        connection,
        [name for (_table, name), _canonical in expected.items()],
    )
    for key, canonical in expected.items():
        definition, validated = actual.get(key, (None, False))
        if not validated or definition is None or not _postgresql_check_matches(definition, canonical):
            return False
    return True


def _postgresql_grac_access_hardened(connection: Connection) -> bool:
    """Return whether GRAC RLS and untrusted-role grants already meet the contract."""
    return not _postgresql_grac_access_gaps(connection, _untrusted_database_roles())


def _postgresql_grac_access_gaps(connection: Connection, roles: tuple[str, ...]) -> list[str]:
    """Return GRAC tables without RLS hardening or reachable by an untrusted role.

    The exact repository-owned runtime policies are verified separately by the
    capability contract in ``src.data.database``. This baseline guard remains
    valid both before capability installation and after policies are present.
    """
    return list(
        connection.execute(
            text(
                "SELECT c.relname FROM pg_class AS c "
                "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = pg_catalog.current_schema() "
                "AND c.relname IN :tables "
                "AND (NOT c.relrowsecurity OR EXISTS ("
                "SELECT 1 FROM aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) "
                "AS acl(grantor, grantee, privilege_type, is_grantable) "
                "WHERE acl.grantee = 0) OR EXISTS (SELECT 1 FROM pg_roles AS rol "
                "WHERE rol.rolname IN :roles AND ("
                "has_table_privilege(rol.oid, c.oid, 'SELECT') "
                "OR has_table_privilege(rol.oid, c.oid, 'INSERT') "
                "OR has_table_privilege(rol.oid, c.oid, 'UPDATE') "
                "OR has_table_privilege(rol.oid, c.oid, 'DELETE') "
                "OR has_table_privilege(rol.oid, c.oid, 'TRUNCATE') "
                "OR has_table_privilege(rol.oid, c.oid, 'REFERENCES') "
                "OR has_table_privilege(rol.oid, c.oid, 'TRIGGER') "
                "OR has_any_column_privilege(rol.oid, c.oid, 'SELECT') "
                "OR has_any_column_privilege(rol.oid, c.oid, 'INSERT') "
                "OR has_any_column_privilege(rol.oid, c.oid, 'UPDATE') "
                "OR has_any_column_privilege(rol.oid, c.oid, 'REFERENCES'))))"
            ).bindparams(
                bindparam("tables", expanding=True),
                bindparam("roles", expanding=True),
            ),
            {"tables": list(GRAC_TABLE_NAMES), "roles": list(roles)},
        )
        .scalars()
        .all()
    )


def list_immutability_trigger_names(table_name: str) -> tuple[str, str, str]:
    """Return stable UPDATE/DELETE/TRUNCATE trigger names for a GRAC table."""
    _require_grac_table(table_name)
    return (
        f"{_TRIGGER_PREFIX}_{table_name}_u",
        f"{_TRIGGER_PREFIX}_{table_name}_d",
        f"{_TRIGGER_PREFIX}_{table_name}_t",
    )


def _require_grac_table(table_name: str) -> None:
    """Reject unknown table names before interpolating DDL identifiers."""
    if table_name not in _GRAC_TABLE_NAME_SET:
        raise ValueError(f"unknown GRAC table for immutability guards: {table_name}")


def _expected_sqlite_trigger_names() -> tuple[str, ...]:
    """Return UPDATE/DELETE trigger names for all GRAC tables."""
    return tuple(name for name, _table, _event in _expected_sqlite_trigger_bindings())


def _expected_sqlite_trigger_bindings() -> frozenset[tuple[str, str, str]]:
    """Return (trigger_name, table_name, event) pairs for SQLite UPDATE/DELETE guards."""
    bindings: set[tuple[str, str, str]] = set()
    for table_name in GRAC_TABLE_NAMES:
        update_name, delete_name, _truncate_name = list_immutability_trigger_names(table_name)
        bindings.add((update_name, table_name, "UPDATE"))
        bindings.add((delete_name, table_name, "DELETE"))
    return frozenset(bindings)


def _expected_postgresql_trigger_names() -> tuple[str, ...]:
    """Return UPDATE/DELETE/TRUNCATE trigger names for all GRAC tables."""
    return tuple(name for name, _table, _event in _expected_postgresql_trigger_bindings())


def _expected_postgresql_trigger_bindings() -> frozenset[tuple[str, str, str]]:
    """Return (trigger_name, table_name, event) bindings for PostgreSQL guards."""
    bindings: set[tuple[str, str, str]] = set()
    for table_name in GRAC_TABLE_NAMES:
        update_name, delete_name, truncate_name = list_immutability_trigger_names(table_name)
        bindings.add((update_name, table_name, "UPDATE"))
        bindings.add((delete_name, table_name, "DELETE"))
        bindings.add((truncate_name, table_name, "TRUNCATE"))
    return frozenset(bindings)


def _sqlite_guards_present(connection: Connection) -> bool:
    """Return True when every GRAC table has its UPDATE and DELETE triggers bound correctly."""
    expected = _expected_sqlite_trigger_bindings()
    rows = connection.execute(
        text("""
            SELECT
                name,
                tbl_name,
                CASE
                    WHEN sql LIKE '%BEFORE UPDATE%' THEN 'UPDATE'
                    WHEN sql LIKE '%BEFORE DELETE%' THEN 'DELETE'
                END AS event
            FROM sqlite_master
            WHERE type = 'trigger'
                AND name IN :names
                AND tbl_name IN :tables
            """).bindparams(
            bindparam("names", expanding=True),
            bindparam("tables", expanding=True),
        ),
        {
            "names": [name for name, _table, _event in expected],
            "tables": list(GRAC_TABLE_NAMES),
        },
    ).fetchall()
    actual = {(row[0], row[1], row[2]) for row in rows if row[2] is not None}
    return actual >= set(expected)


def _postgresql_guards_present(connection: Connection) -> bool:
    """Return True when the function and all current-schema GRAC trigger bindings exist."""
    row = connection.execute(
        text("""
            SELECT 1
            FROM pg_proc AS p
            JOIN pg_namespace AS n ON n.oid = p.pronamespace
            WHERE p.proname = :name
                AND p.pronargs = 0
                AND n.nspname = pg_catalog.current_schema()
                AND COALESCE(p.proconfig, ARRAY[]::text[]) @> ARRAY['search_path=pg_catalog']
            """),
        {"name": _IMMUTABILITY_FUNCTION},
    ).first()
    if row is None:
        return False
    expected = _expected_postgresql_trigger_bindings()
    # tgtype bits: ROW=1, BEFORE=2, DELETE=8, UPDATE=16, TRUNCATE=32 (PostgreSQL trigger.h).
    # tgenabled: O=origin, D=disabled, R=replica, A=always.
    # Require O/A so replica-only (R) and disabled (D) guards force reinstall/repair.
    rows = connection.execute(
        text("""
            SELECT
                t.tgname,
                c.relname,
                CASE
                    WHEN (t.tgtype & 16) <> 0
                        AND (t.tgtype & 2) <> 0
                        AND (t.tgtype & 1) <> 0
                    THEN 'UPDATE'
                    WHEN (t.tgtype & 8) <> 0
                        AND (t.tgtype & 2) <> 0
                        AND (t.tgtype & 1) <> 0
                    THEN 'DELETE'
                    WHEN (t.tgtype & 32) <> 0
                        AND (t.tgtype & 2) <> 0
                        AND (t.tgtype & 1) = 0
                    THEN 'TRUNCATE'
                END AS event
            FROM pg_trigger AS t
            JOIN pg_class AS c ON c.oid = t.tgrelid
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            JOIN pg_proc AS p ON p.oid = t.tgfoid
            JOIN pg_namespace AS fn_ns ON fn_ns.oid = p.pronamespace
            WHERE t.tgname IN :names
                AND n.nspname = pg_catalog.current_schema()
                AND c.relname IN :tables
                AND NOT t.tgisinternal
                AND t.tgenabled IN ('O', 'A')
                AND fn_ns.nspname = pg_catalog.current_schema()
                AND p.proname = :fn
                AND p.pronargs = 0
            """).bindparams(
            bindparam("names", expanding=True),
            bindparam("tables", expanding=True),
        ),
        {
            "names": [name for name, _table, _event in expected],
            "tables": list(GRAC_TABLE_NAMES),
            "fn": _IMMUTABILITY_FUNCTION,
        },
    ).fetchall()
    actual = {(row[0], row[1], row[2]) for row in rows if row[2] is not None}
    return actual >= set(expected)


def _untrusted_database_roles(environment: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Resolve untrusted DB roles; same contract as check_database_authorization."""
    env = os.environ if environment is None else environment
    raw_roles = env.get(_UNTRUSTED_DATABASE_ROLES_ENV)
    if raw_roles is None:
        return _DEFAULT_UNTRUSTED_DATABASE_ROLES
    roles = tuple(dict.fromkeys(role.strip() for role in raw_roles.split(",")))
    if not roles or any(not _SAFE_ROLE_PATTERN.fullmatch(role) for role in roles):
        raise ValueError(
            f"invalid {_UNTRUSTED_DATABASE_ROLES_ENV}; expected comma-separated "
            "role identifiers matching ^[a-z_][a-z0-9_]*$"
        )
    return roles


def _immutability_function_has_untrusted_execute(
    connection: Connection,
    untrusted_roles: tuple[str, ...],
) -> bool:
    """Return True if PUBLIC or configured untrusted roles still have EXECUTE.

    PUBLIC is checked via ``aclexplode`` grantee 0 (direct ACL only). Untrusted
    roles use inheritance-aware ``has_function_privilege``, matching
    ``scripts/check_database_authorization.py``. Missing roles are skipped by
    the ``pg_roles`` join.
    """
    return bool(
        connection.execute(
            text("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc AS p
                JOIN pg_namespace AS n ON n.oid = p.pronamespace
                WHERE p.proname = :name
                    AND p.pronargs = 0
                    AND n.nspname = pg_catalog.current_schema()
                    AND (
                        EXISTS (
                            SELECT 1
                            FROM aclexplode(
                                COALESCE(p.proacl, acldefault('f', p.proowner))
                            ) AS acl(grantor, grantee, privilege_type, is_grantable)
                            WHERE acl.privilege_type = 'EXECUTE'
                                AND acl.grantee = 0
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM pg_roles AS rol
                            WHERE rol.rolname IN :roles
                                AND has_function_privilege(
                                    rol.oid, p.oid, 'EXECUTE'
                                )
                        )
                    )
            )
            """).bindparams(bindparam("roles", expanding=True)),
            {"name": _IMMUTABILITY_FUNCTION, "roles": list(untrusted_roles)},
        ).scalar()
    )


def _install_sqlite_immutability_guards(connection: Connection) -> None:
    """Install DROP+CREATE BEFORE UPDATE/DELETE triggers for SQLite."""
    for table_name in GRAC_TABLE_NAMES:
        _require_grac_table(table_name)
        update_name, delete_name, _truncate_name = list_immutability_trigger_names(table_name)
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name}"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS {delete_name}"))
        update_trigger_sql = f"""
                CREATE TRIGGER {update_name}
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'GRAC v1 immutability: UPDATE forbidden on {table_name}');
                END
                """
        delete_trigger_sql = f"""
                CREATE TRIGGER {delete_name}
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'GRAC v1 immutability: DELETE forbidden on {table_name}');
                END
                """
        connection.execute(text(update_trigger_sql))
        connection.execute(text(delete_trigger_sql))
