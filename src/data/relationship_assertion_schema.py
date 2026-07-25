"""Dialect-aware GRAC v1 assertion schema helpers.

``Base.metadata.create_all`` creates the seven additive tables. This module
installs idempotent immutability guards (SQLite + PostgreSQL triggers) that
reject UPDATE/DELETE on all seven append-only tables.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from src.data.relationship_assertion_db_models import GRAC_TABLE_NAMES

# Trigger / function names are stable so re-init is idempotent.
_IMMUTABILITY_FUNCTION = "grac_v1_reject_mutation"
_TRIGGER_PREFIX = "grac_v1_immutability"


def ensure_relationship_assertion_schema(engine: Engine) -> None:
    """
    Ensure GRAC assertion tables have dialect-appropriate immutability guards.

    Tables themselves are created by ``Base.metadata.create_all`` after the ORM
    models are imported. This helper is safe to call repeatedly.
    """
    backend = engine.dialect.name
    with engine.begin() as connection:
        if backend == "sqlite":
            _install_sqlite_immutability_guards(connection)
        elif backend == "postgresql":
            _install_postgresql_immutability_guards(connection)
        else:
            # Unknown dialects: tables may exist via create_all; no guards.
            return


def list_immutability_trigger_names(table_name: str) -> tuple[str, str]:
    """Return stable UPDATE/DELETE trigger names for a GRAC table."""
    return (
        f"{_TRIGGER_PREFIX}_{table_name}_update",
        f"{_TRIGGER_PREFIX}_{table_name}_delete",
    )


def _install_sqlite_immutability_guards(connection: Connection) -> None:
    """Install DROP+CREATE BEFORE UPDATE/DELETE triggers for SQLite."""
    for table_name in GRAC_TABLE_NAMES:
        update_name, delete_name = list_immutability_trigger_names(table_name)
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
    """Install a shared RAISE function and BEFORE UPDATE/DELETE triggers for PostgreSQL."""
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
    for table_name in GRAC_TABLE_NAMES:
        update_name, delete_name = list_immutability_trigger_names(table_name)
        connection.execute(text(f"DROP TRIGGER IF EXISTS {update_name} ON {table_name}"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS {delete_name} ON {table_name}"))
        connection.execute(text(f"""
                CREATE TRIGGER {update_name}
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE PROCEDURE {_IMMUTABILITY_FUNCTION}()
                """))
        connection.execute(text(f"""
                CREATE TRIGGER {delete_name}
                BEFORE DELETE ON {table_name}
                FOR EACH ROW
                EXECUTE PROCEDURE {_IMMUTABILITY_FUNCTION}()
                """))
