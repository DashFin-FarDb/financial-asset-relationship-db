"""Prove runtime topology from live cluster and database identities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from .database import SchemaCompatibilityError


class RuntimeIdentityUnavailable(SchemaCompatibilityError):
    """Identity access or response was insufficient to establish runtime topology."""


@dataclass(frozen=True)
class DatabaseIdentity:
    """Identify a database within the cluster lineage initialized by PostgreSQL."""

    system_identifier: str
    database_oid: int
    database_name: str


def read_database_identity(connection) -> DatabaseIdentity:
    """Read identity on the connection that will perform authority verification."""
    try:
        rows = connection.execute(
            text(
                "SELECT control.system_identifier::text, database.oid::bigint, database.datname "
                "FROM pg_catalog.pg_control_system() AS control "
                "JOIN pg_catalog.pg_database AS database ON database.datname = pg_catalog.current_database()"
            )
        ).fetchall()
        if len(rows) != 1 or len(rows[0]) != 3:
            raise ValueError("ambiguous identity")
        identifier, oid, name = rows[0]
        if not isinstance(identifier, str) or not identifier.isascii() or not identifier.isdecimal():
            raise ValueError("invalid cluster identity")
        if int(identifier) <= 0 or not isinstance(oid, int) or oid <= 0 or not isinstance(name, str) or not name:
            raise ValueError("invalid database identity")
        return DatabaseIdentity(identifier, oid, name)
    except Exception as exc:
        raise RuntimeIdentityUnavailable("runtime cluster/database identity could not be established") from exc


def same_database(left: DatabaseIdentity, right: DatabaseIdentity) -> bool:
    """Require both cluster lineage and database identity to agree."""
    return left == right
