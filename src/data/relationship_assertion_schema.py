"""Dialect-aware GRAC v1 assertion schema helpers.

``Base.metadata.create_all`` creates the seven additive tables. This module
installs idempotent immutability guards (SQLite + PostgreSQL triggers) that
reject UPDATE/DELETE (and PostgreSQL TRUNCATE) on all seven append-only tables.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine, make_url

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
    Ensure GRAC assertion tables have dialect-appropriate immutability guards.

    Tables themselves are created by ``Base.metadata.create_all`` after the ORM
    models are imported. When all guards are already present this skips DDL so a
    least-privilege runtime role without CREATE rights can restart safely.
    Privilege repair (REVOKE PUBLIC/untrusted EXECUTE) still runs on PostgreSQL
    whenever the immutability function exists, and raises if PUBLIC or existing
    untrusted roles retain EXECUTE.
    """
    backend = make_url(str(engine.url)).get_backend_name()
    with engine.begin() as connection:
        _ensure_projection_revision_scope_metadata(connection, backend)
        if backend == "sqlite":
            _require_sqlite_grac_constraints(connection)
            if not _sqlite_guards_present(connection):
                _install_sqlite_immutability_guards(connection)
        elif backend == "postgresql":
            _ensure_postgresql_grac_constraints(connection)
            if not _postgresql_guards_present(connection):
                _install_postgresql_immutability_guards(connection)
            else:
                # Upgrade path: earlier installs may have left untrusted EXECUTE.
                _revoke_immutability_function_execute(connection)
            if not _postgresql_grac_access_hardened(connection):
                _harden_postgresql_grac_access(connection)


def _ensure_projection_revision_scope_metadata(connection: Connection, backend: str) -> None:
    """Add durable scope metadata and the successor FK index on upgrade."""
    requires_backfill = False
    if backend == "sqlite":
        rows = connection.execute(text("PRAGMA table_info(relationship_projection_revisions)")).fetchall()
        column_names = {row[1] for row in rows}
    elif backend == "postgresql":
        column_names = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'relationship_projection_revisions'"
                )
            )
        }
    else:
        return
    if "governed_scopes" not in column_names:
        requires_backfill = True
        connection.execute(
            text(
                "ALTER TABLE relationship_projection_revisions " "ADD COLUMN governed_scopes TEXT NOT NULL DEFAULT '[]'"
            )
        )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_relationship_assertion_events_successor_assertion_id "
            "ON relationship_assertion_events (successor_assertion_id)"
        )
    )
    if requires_backfill:
        _backfill_projection_revision_scopes(connection, backend)


def _backfill_projection_revision_scopes(connection: Connection, backend: str) -> None:
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
    _allow_projection_revision_backfill(connection, backend)
    try:
        connection.execute(
            text(
                "UPDATE relationship_projection_revisions "
                "SET governed_scopes = :governed_scopes WHERE id = :revision_id"
            ),
            payloads,
        )
    finally:
        _restore_projection_revision_immutability(connection, backend)


def _allow_projection_revision_backfill(connection: Connection, backend: str) -> None:
    """Temporarily disable revision guards inside an owner migration transaction."""
    if backend == "postgresql":
        connection.execute(text("ALTER TABLE relationship_projection_revisions DISABLE TRIGGER USER"))
        return
    update_name, _delete_name, _truncate_name = list_immutability_trigger_names("relationship_projection_revisions")
    connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name}"))


def _restore_projection_revision_immutability(connection: Connection, backend: str) -> None:
    """Restore the revision immutability guard after controlled metadata backfill."""
    if backend == "postgresql":
        connection.execute(text("ALTER TABLE relationship_projection_revisions ENABLE TRIGGER USER"))
        return
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


def _ensure_postgresql_grac_constraints(connection: Connection) -> None:
    """Install and validate new GRAC CHECKs; validation fails closed on invalid history."""
    constraints = (
        ("relationship_assertions", "ck_relationship_assertions_effective_window", EFFECTIVE_WINDOW_CHECK),
        ("relationship_projection_edges", "ck_relationship_projection_edges_strength", STRENGTH_DECIMAL_CHECK),
    )
    rows = connection.execute(
        text(
            "SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid), con.convalidated "
            "FROM pg_constraint AS con "
            "JOIN pg_class AS rel ON rel.oid = con.conrelid "
            "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
            "WHERE namespace.nspname = current_schema() AND con.conname IN :names"
        ).bindparams(bindparam("names", expanding=True)),
        {"names": [name for _table, name, _check in constraints]},
    ).all()
    existing = {(table, name): (definition, validated) for table, name, definition, validated in rows}
    for table, name, check in constraints:
        current = existing.get((table, name))
        if current is not None and (name.endswith("strength") and "replace" not in current[0]):
            connection.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {name}"))
            current = None
        if current is None:
            connection.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({check}) NOT VALID"))
        connection.execute(text(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}"))


def _harden_postgresql_grac_access(connection: Connection) -> None:
    """Enable RLS and revoke public/untrusted table grants without adding policies."""
    roles = _untrusted_database_roles()
    for table_name in GRAC_TABLE_NAMES:
        _require_grac_table(table_name)
        connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table_name} FROM PUBLIC"))
        for role in roles:
            connection.execute(
                text(
                    f"DO $revoke$ BEGIN EXECUTE format("
                    f"'REVOKE ALL PRIVILEGES ON TABLE %I.%I FROM %I', "
                    f"pg_catalog.current_schema(), '{table_name}', '{role}'); "
                    f"EXCEPTION WHEN undefined_object THEN NULL; END $revoke$"
                )
            )
    insecure = _postgresql_grac_access_gaps(connection, roles)
    if insecure:
        raise PermissionError(f"GRAC RLS/grant hardening failed for tables: {sorted(insecure)}")


def _postgresql_grac_access_hardened(connection: Connection) -> bool:
    """Return whether GRAC RLS and untrusted-role grants already meet the contract."""
    return not _postgresql_grac_access_gaps(connection, _untrusted_database_roles())


def _postgresql_grac_access_gaps(connection: Connection, roles: tuple[str, ...]) -> list[str]:
    """Return GRAC tables without RLS hardening or reachable by an untrusted role."""
    return list(
        connection.execute(
            text(
                "SELECT c.relname FROM pg_class AS c "
                "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = pg_catalog.current_schema() "
                "AND c.relname IN :tables "
                "AND (NOT c.relrowsecurity OR EXISTS ("
                "SELECT 1 FROM pg_policy AS p WHERE p.polrelid = c.oid) OR EXISTS ("
                "SELECT 1 FROM aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) "
                "AS acl(grantor, grantee, privilege_type, is_grantable) "
                "WHERE acl.grantee = 0) OR EXISTS (SELECT 1 FROM pg_roles AS rol "
                "WHERE rol.rolname IN :roles AND (has_table_privilege(rol.oid, c.oid, "
                "'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER') "
                "OR has_any_column_privilege(rol.oid, c.oid, "
                "'SELECT, INSERT, UPDATE, REFERENCES'))))"
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


def _immutability_revoke_sql(untrusted_roles: tuple[str, ...]) -> str:
    """Build schema-qualified REVOKE DO-block for PUBLIC and untrusted roles."""
    role_placeholders = ", ".join("%I" for _ in untrusted_roles)
    role_format_args = ",\n                        ".join(f"'{role}'" for role in untrusted_roles)
    return f"""
            DO $revoke$
            BEGIN
                BEGIN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON FUNCTION %I.%I() FROM PUBLIC',
                        pg_catalog.current_schema(),
                        '{_IMMUTABILITY_FUNCTION}'
                    );
                EXCEPTION
                    WHEN insufficient_privilege THEN
                        NULL;
                END;
                BEGIN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON FUNCTION %I.%I() FROM {role_placeholders}',
                        pg_catalog.current_schema(),
                        '{_IMMUTABILITY_FUNCTION}',
                        {role_format_args}
                    );
                EXCEPTION
                    WHEN undefined_object THEN
                        NULL;
                    WHEN insufficient_privilege THEN
                        NULL;
                END;
            END
            $revoke$;
            """


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


def _revoke_immutability_function_execute(connection: Connection) -> None:
    """Revoke PUBLIC/untrusted EXECUTE on the current-schema raise function; fail if any retain it.

    Scoped to ``pg_catalog.current_schema()`` so a same-named function in another
    schema with PUBLIC EXECUTE cannot block startup or receive REVOKE.
    After REVOKE, verify neither PUBLIC nor configured untrusted roles
    (``FARDB_UNTRUSTED_DATABASE_ROLES``, default ``anon``/``authenticated``)
    retain EXECUTE — aligned with ``scripts/check_database_authorization.py``.
    Missing untrusted roles stay non-fatal via ``undefined_object`` suppression.
    """
    untrusted_roles = _untrusted_database_roles()
    # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
    connection.execute(text(_immutability_revoke_sql(untrusted_roles)))
    if _immutability_function_has_untrusted_execute(connection, untrusted_roles):
        raise PermissionError(
            f"insufficient privilege to revoke PUBLIC/untrusted EXECUTE on {_IMMUTABILITY_FUNCTION}(); "
            "restart as the function owner or a role that can REVOKE"
        )


def _install_sqlite_immutability_guards(connection: Connection) -> None:
    """Install DROP+CREATE BEFORE UPDATE/DELETE triggers for SQLite."""
    for table_name in GRAC_TABLE_NAMES:
        _require_grac_table(table_name)
        update_name, delete_name, _truncate_name = list_immutability_trigger_names(table_name)
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name}"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS {delete_name}"))
        connection.execute(text(f"""
                CREATE TRIGGER {update_name}
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'GRAC v1 immutability: UPDATE forbidden on {table_name}');
                END
                """))
        connection.execute(text(f"""
                CREATE TRIGGER {delete_name}
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'GRAC v1 immutability: DELETE forbidden on {table_name}');
                END
                """))


def _install_postgresql_immutability_guards(connection: Connection) -> None:
    """Install a shared RAISE function and BEFORE UPDATE/DELETE/TRUNCATE triggers."""
    # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
    connection.execute(text(f"""
            CREATE OR REPLACE FUNCTION {_IMMUTABILITY_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path TO pg_catalog
            AS $$
            BEGIN
                RAISE EXCEPTION 'GRAC v1 immutability: % forbidden on %',
                    TG_OP, TG_TABLE_NAME
                    USING ERRCODE = 'integrity_constraint_violation';
            END;
            $$
            """))
    _revoke_immutability_function_execute(connection)

    for table_name in GRAC_TABLE_NAMES:
        _require_grac_table(table_name)
        update_name, delete_name, truncate_name = list_immutability_trigger_names(table_name)
        connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name} ON {table_name}"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS {delete_name} ON {table_name}"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS {truncate_name} ON {table_name}"))
        connection.execute(text(f"""
                CREATE TRIGGER {update_name}
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION {_IMMUTABILITY_FUNCTION}()
                """))
        connection.execute(text(f"""
                CREATE TRIGGER {delete_name}
                BEFORE DELETE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION {_IMMUTABILITY_FUNCTION}()
                """))
        connection.execute(text(f"""
                CREATE TRIGGER {truncate_name}
                BEFORE TRUNCATE ON {table_name}
                FOR EACH STATEMENT
                EXECUTE FUNCTION {_IMMUTABILITY_FUNCTION}()
                """))
