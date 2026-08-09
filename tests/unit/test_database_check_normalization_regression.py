"""Regression coverage for PostgreSQL CHECK-constraint deparsing."""

from __future__ import annotations

import pytest

from src.data.database import _normalize_check_definition

pytestmark = pytest.mark.unit


def test_check_normalization_accepts_nullable_postgresql_any_rendering() -> None:
    """Nullable IN predicates must survive PostgreSQL's ANY/ARRAY deparse."""
    expected = (
        "from_state IS NULL OR from_state IN ("
        "'Proposed', 'Accepted', 'Rejected', 'Withdrawn', "
        "'Disputed', 'Retracted', 'Superseded')"
    )
    reflected = (
        "CHECK (from_state IS NULL OR (from_state::text = ANY (ARRAY["
        "'Proposed'::character varying, 'Accepted'::character varying, "
        "'Rejected'::character varying, 'Withdrawn'::character varying, "
        "'Disputed'::character varying, 'Retracted'::character varying, "
        "'Superseded'::character varying]::text[])))"
    )

    assert _normalize_check_definition(reflected) == _normalize_check_definition(expected)


def test_check_normalization_preserves_boolean_grouping() -> None:
    """Redundant-parenthesis cleanup must not weaken AND/OR precedence."""
    left = "CHECK (a AND (b OR c))"
    right = "CHECK ((a AND b) OR c)"

    assert _normalize_check_definition(left) != _normalize_check_definition(right)
