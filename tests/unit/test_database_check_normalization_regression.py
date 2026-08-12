"""Regression coverage for PostgreSQL CHECK-constraint deparsing."""

from __future__ import annotations

import pytest

from src.data.database import _normalize_check_definition
from src.data.relationship_assertion_db_models import STRENGTH_DECIMAL_CHECK

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


def test_check_normalization_accepts_strength_postgresql_deparse() -> None:
    """Function-call BETWEEN operands must match PostgreSQL's expanded bounds."""
    reflected = (
        "CHECK ((((length((strength)::text) >= 1) AND (length((strength)::text) <= 32)) "
        "AND (translate((strength)::text, '0123456789.'::text, ''::text) = ''::text) "
        "AND ((strength)::text !~~ '.%'::text) AND ((strength)::text !~~ '%.'::text) "
        "AND ((strength)::text !~~ '%..%'::text) AND ((strength)::text !~~ '%.%.%'::text) "
        "AND (((strength)::text = '0'::text) OR ((strength)::text = '1'::text) "
        "OR ((strength)::text ~~ '0.%'::text) OR (((strength)::text ~~ '1.%'::text) "
        "AND (replace(substr((strength)::text, 3), '0'::text, ''::text) = ''::text)))))"
    )

    assert _normalize_check_definition(reflected) == _normalize_check_definition(STRENGTH_DECIMAL_CHECK)


@pytest.mark.parametrize(
    ("between", "expanded"),
    [
        ("CHECK (score BETWEEN 1 AND 10)", "CHECK (score >= 1 AND score <= 10)"),
        ("CHECK ((score) BETWEEN 1 AND 10)", "CHECK ((score) >= 1 AND (score) <= 10)"),
        (
            "CHECK (length(trim(strength)) BETWEEN 1 AND 32)",
            "CHECK (length(trim(strength)) >= 1 AND length(trim(strength)) <= 32)",
        ),
    ],
)
def test_check_normalization_expands_between_with_linear_parser(between: str, expanded: str) -> None:
    """Simple and nested-call operands must normalize without backtracking regexes."""
    assert _normalize_check_definition(between) == _normalize_check_definition(expanded)
