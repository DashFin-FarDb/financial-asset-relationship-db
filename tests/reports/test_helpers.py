from __future__ import annotations

import pytest

from src.reports.helpers import (
    _as_float,
    _as_int,
    _as_str_int_map,
    _as_top_relationships,
)

# ---------------------------------------------------------------------------
# _as_int tests
# ---------------------------------------------------------------------------


def test_as_int_valid_conversion() -> None:
    assert _as_int("10") == 10
    assert _as_int(5) == 5


def test_as_int_invalid_conversion() -> None:
    assert _as_int(None, default=3) == 3
    assert _as_int("x", default=2) == 2
    assert _as_int(object(), default=-1) == -1


# ---------------------------------------------------------------------------
# _as_float tests
# ---------------------------------------------------------------------------


def test_as_float_valid_conversion() -> None:
    assert _as_float("1.5") == 1.5
    assert _as_float(2) == 2.0


def test_as_float_invalid_conversion() -> None:
    assert _as_float(None, default=9.9) == 9.9
    assert _as_float("bad", default=-0.5) == -0.5
    assert _as_float(object(), default=7.0) == 7.0


# ---------------------------------------------------------------------------
# _as_str_int_map tests
# ---------------------------------------------------------------------------


def test_as_str_int_map_valid() -> None:
    src = {"a": "1", "b": 2, 3: "not included"}
    out = _as_str_int_map(src)
    assert out == {"a": 1, "b": 2}


def test_as_str_int_map_non_mapping() -> None:
    assert _as_str_int_map(123) == {}
    assert _as_str_int_map(["x", "y"]) == {}


# ---------------------------------------------------------------------------
# _as_top_relationships tests
# ---------------------------------------------------------------------------


def test_as_top_relationships_valid() -> None:
    src = [
        ("A", "B", "correlation", "0.8"),
        ("X", "Y", "hedge", 0.2),
    ]
    out = _as_top_relationships(src)

    assert out == [
        ("A", "B", "correlation", 0.8),
        ("X", "Y", "hedge", 0.2),
    ]


def test_as_top_relationships_filters_invalid() -> None:
    """
    Verifies that _as_top_relationships filters out malformed relationship entries and normalizes strengths.

    Ensures entries with incorrect tuple length or a non-string relationship type are dropped, and entries with non-numeric strength default their strength to 0.0 while preserving valid src, dst, and relationship values.
    """
    src = [
        ("A", "B", "invalid"),  # too short
        ("A", "B", 5, 0.5),  # non-str relationship type
        ("A", "B", "C", "bad-num"),  # strength fallback to 0.0
    ]
    out = _as_top_relationships(src)

    assert out == [
        ("A", "B", "C", 0.0),
    ]


def test_as_top_relationships_non_iterable() -> None:
    assert _as_top_relationships(123) == []
