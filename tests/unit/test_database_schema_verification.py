"""Unit tests for database schema compatibility verification helpers."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, MetaData, String, Table, UniqueConstraint

from src.data.database import (
    Base,
    SchemaCompatibilityError,
    _normalize_check_definition,
    _verify_table_constraints,
    _verify_table_schema,
)

pytestmark = pytest.mark.unit


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """Provide an isolated declarative base for table-contract tests."""
    existing_tables = set(Base.metadata.tables)

    class _IsolatedBase(Base):
        """Declarative base subclass whose tables are cleaned after the test."""

        __abstract__ = True

    yield _IsolatedBase

    for table_name in set(Base.metadata.tables) - existing_tables:
        Base.metadata.remove(Base.metadata.tables[table_name])


@pytest.mark.parametrize(
    "missing_invariant, error_match",
    [
        ("primary_key", "primary-key"),
        ("unique", "uniqueness"),
        ("foreign_key", "foreign-key"),
    ],
)
def test_table_constraint_verifier_rejects_missing_invariants(missing_invariant: str, error_match: str) -> None:
    """Runtime verification must cover PK, exact uniqueness, and FK contracts."""
    metadata = MetaData()
    Table("parent", metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String),
        Column("parent_id", ForeignKey("parent.id")),
        UniqueConstraint("code"),
    )
    inspector = MagicMock()
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    inspector.get_unique_constraints.return_value = [{"column_names": ["code"]}]
    inspector.get_foreign_keys.return_value = [
        {
            "constrained_columns": ["parent_id"],
            "referred_table": "parent",
            "referred_columns": ["id"],
        }
    ]
    if missing_invariant == "primary_key":
        inspector.get_pk_constraint.return_value = {"constrained_columns": []}
    elif missing_invariant == "unique":
        inspector.get_unique_constraints.return_value = []
    else:
        inspector.get_foreign_keys.return_value = []

    with pytest.raises(SchemaCompatibilityError, match=error_match):
        _verify_table_constraints(inspector, "child", child)


def test_check_normalization_accepts_postgresql_any_rendering() -> None:
    """PostgreSQL deparsing should preserve an equivalent literal status domain."""
    expected = "status IN ('pending', 'running', 'cancelled')"
    reflected = (
        "CHECK (((status)::text = ANY ((ARRAY['running'::character varying, "
        "'cancelled'::character varying, 'pending'::character varying])::text[])))"
    )
    assert _normalize_check_definition(reflected) == _normalize_check_definition(expected)


@pytest.mark.parametrize(
    ("mismatch", "error_match"),
    [("check", "incompatible constraints"), ("index", "incompatible indexes")],
)
def test_table_schema_rejects_same_named_definition_drift(
    mismatch: str,
    error_match: str,
    isolated_base: type[Base],
) -> None:
    """Names alone must not admit changed CHECK predicates or index properties."""

    class ContractModel(isolated_base):  # type: ignore[misc]
        """Isolated schema contract for reflected-definition checks."""

        __tablename__ = "definition_contract"
        __table_args__ = (
            CheckConstraint("value >= 0", name="ck_definition_contract_value"),
            Index("ix_definition_contract_value", "value"),
        )
        id = Column(Integer, primary_key=True)
        value = Column(Integer)

    inspector = MagicMock()
    inspector.get_columns.return_value = [{"name": "id"}, {"name": "value"}]
    inspector.get_check_constraints.return_value = [
        {
            "name": "ck_definition_contract_value",
            "sqltext": "value >= 1" if mismatch == "check" else "value >= 0",
        }
    ]
    inspector.get_indexes.return_value = [
        {
            "name": "ix_definition_contract_value",
            "column_names": ["id" if mismatch == "index" else "value"],
            "unique": False,
        }
    ]
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    inspector.get_unique_constraints.return_value = []
    inspector.get_foreign_keys.return_value = []

    with pytest.raises(SchemaCompatibilityError, match=error_match):
        _verify_table_schema(inspector, ContractModel.__tablename__)
