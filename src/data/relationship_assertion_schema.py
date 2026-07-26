"""Dialect-aware GRAC v1 assertion schema helpers.

``Base.metadata.create_all`` creates the seven additive tables. This module
installs idempotent immutability guards (SQLite + PostgreSQL triggers) that
reject UPDATE/DELETE (and PostgreSQL TRUNCATE) on all seven append-only tables.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine, make_url

from src.data.relationship_assertion_db_models import GRAC_TABLE_NAMES

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
        if backend == "sqlite":
            if not _sqlite_guards_present(connection):
                _install_sqlite_immutability_guards(connection)
        elif backend == "postgresql":
            if not _postgresql_guards_present(connection):
                _install_postgresql_immutability_guards(connection)
            else:
                # Upgrade path: earlier installs may have left untrusted EXECUTE.
                _revoke_immutability_function_execute(connection)


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
    names: list[str] = []
    for table_name in GRAC_TABLE_NAMES:
        update_name, delete_name, _truncate_name = list_immutability_trigger_names(table_name)
        names.extend((update_name, delete_name))
    return tuple(names)


def _expected_postgresql_trigger_names() -> tuple[str, ...]:
    """Return UPDATE/DELETE/TRUNCATE trigger names for all GRAC tables."""
    names: list[str] = []
    for table_name in GRAC_TABLE_NAMES:
        names.extend(list_immutability_trigger_names(table_name))
    return tuple(names)


def _sqlite_guards_present(connection: Connection) -> bool:
    """Return True when every GRAC table has UPDATE and DELETE triggers."""
    expected = _expected_sqlite_trigger_names()
    rows = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND name IN :names").bindparams(
            bindparam("names", expanding=True)
        ),
        {"names": list(expected)},
    ).fetchall()
    return {row[0] for row in rows} >= set(expected)


def _postgresql_guards_present(connection: Connection) -> bool:
    """Return True when the function and all table triggers exist."""
    row = connection.execute(
        text("""
            SELECT 1
            FROM pg_proc AS p
            JOIN pg_namespace AS n ON n.oid = p.pronamespace
            WHERE p.proname = :name
                AND p.pronargs = 0
                AND n.nspname = pg_catalog.current_schema()
            """),
        {"name": _IMMUTABILITY_FUNCTION},
    ).first()
    if row is None:
        return False
    expected = _expected_postgresql_trigger_names()
    rows = connection.execute(
        text("SELECT tgname FROM pg_trigger WHERE tgname IN :names").bindparams(bindparam("names", expanding=True)),
        {"names": list(expected)},
    ).fetchall()
    return {row[0] for row in rows} >= set(expected)


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
    role_placeholders = ", ".join("%I" for _ in untrusted_roles)
    role_format_args = ",\n                        ".join(f"'{role}'" for role in untrusted_roles)
    # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
    connection.execute(text(f"""
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
            """))
    # aclexplode grantee 0 is PUBLIC; default ACL still grants PUBLIC EXECUTE.
    # Also reject explicit EXECUTE to configured untrusted roles when they exist.
    # Limit to the zero-arg function in the active schema (trigger target), not every proname match.
    untrusted_execute = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc AS p
                JOIN pg_namespace AS n ON n.oid = p.pronamespace
                CROSS JOIN LATERAL aclexplode(
                    COALESCE(p.proacl, acldefault('f', p.proowner))
                ) AS acl(grantor, grantee, privilege_type, is_grantable)
                WHERE p.proname = :name
                    AND p.pronargs = 0
                    AND n.nspname = pg_catalog.current_schema()
                    AND acl.privilege_type = 'EXECUTE'
                    AND (
                        acl.grantee = 0
                        OR acl.grantee IN (
                            SELECT oid
                            FROM pg_roles
                            WHERE rolname IN :roles
                        )
                    )
            )
            """).bindparams(bindparam("roles", expanding=True)),
        {"name": _IMMUTABILITY_FUNCTION, "roles": list(untrusted_roles)},
    ).scalar()
    if untrusted_execute:
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
