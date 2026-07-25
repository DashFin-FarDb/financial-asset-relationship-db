"""Dialect-aware GRAC v1 assertion schema helpers.

``Base.metadata.create_all`` creates the seven additive tables. This module
installs idempotent immutability guards (SQLite + PostgreSQL triggers) that
reject UPDATE/DELETE (and PostgreSQL TRUNCATE) on all seven append-only tables.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, make_url

from src.data.relationship_assertion_db_models import GRAC_TABLE_NAMES

# Keep names well under PostgreSQL's 63-byte identifier limit for every table.
_IMMUTABILITY_FUNCTION = "grac_v1_reject_mutation"
_TRIGGER_PREFIX = "grac_imm"
_GRAC_TABLE_NAME_SET = frozenset(GRAC_TABLE_NAMES)


def ensure_relationship_assertion_schema(engine: Engine) -> None:
    """
    Ensure GRAC assertion tables have dialect-appropriate immutability guards.

    Tables themselves are created by ``Base.metadata.create_all`` after the ORM
    models are imported. When guards are already present this is a no-op so a
    least-privilege runtime role without DDL rights can restart safely.
    """
    backend = make_url(str(engine.url)).get_backend_name()
    with engine.begin() as connection:
        if backend == "sqlite":
            if _sqlite_guards_present(connection):
                return
            _install_sqlite_immutability_guards(connection)
            return
        if backend == "postgresql":
            if _postgresql_guards_present(connection):
                return
            _install_postgresql_immutability_guards(connection)
            return


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


def _sqlite_guards_present(connection: Connection) -> bool:
    """Return True when the first table's UPDATE trigger already exists."""
    update_name, _, _ = list_immutability_trigger_names(GRAC_TABLE_NAMES[0])
    row = connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = :name"),
        {"name": update_name},
    ).first()
    return row is not None


def _postgresql_guards_present(connection: Connection) -> bool:
    """Return True when the shared immutability function already exists."""
    row = connection.execute(
        text("SELECT 1 FROM pg_proc WHERE proname = :name"),
        {"name": _IMMUTABILITY_FUNCTION},
    ).first()
    return row is not None


def _install_sqlite_immutability_guards(connection: Connection) -> None:
    """Install DROP+CREATE BEFORE UPDATE/DELETE triggers for SQLite."""
    for table_name in GRAC_TABLE_NAMES:
        _require_grac_table(table_name)
        update_name, delete_name, _truncate_name = list_immutability_trigger_names(table_name)
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
    # Match ADR 0007 / migration 005: do not leave PUBLIC EXECUTE on new functions.
    # anon/authenticated may be absent in local/ephemeral Postgres — ignore that case.
    connection.execute(text(f"""
            DO $revoke$
            BEGIN
                EXECUTE 'REVOKE ALL PRIVILEGES ON FUNCTION {_IMMUTABILITY_FUNCTION}() FROM PUBLIC';
                BEGIN
                    EXECUTE 'REVOKE ALL PRIVILEGES ON FUNCTION {_IMMUTABILITY_FUNCTION}() '
                        'FROM anon, authenticated';
                EXCEPTION
                    WHEN undefined_object THEN
                        NULL;
                END;
            END
            $revoke$;
            """))

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
