from __future__ import annotations

import pytest

from src.reports.helpers import (
    _as_float,
    _as_int,
    _as_str_int_map,
    _as_top_relationships,
)

pytestmark = pytest.mark.unit

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


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


def test_as_int_with_float() -> None:
    """Test _as_int with float values."""
    assert _as_int(3.7) == 3
    assert _as_int(10.0) == 10
    assert _as_int(-5.9) == -5


def test_as_int_with_boolean() -> None:
    """Test _as_int with boolean values."""
    assert _as_int(True) == 1
    assert _as_int(False) == 0


def test_as_int_with_large_numbers() -> None:
    """Test _as_int with large numbers."""
    assert _as_int(1_000_000) == 1_000_000
    assert _as_int("999999999") == 999999999


def test_as_float_with_scientific_notation() -> None:
    """Test _as_float with scientific notation."""
    assert _as_float("1e3") == pytest.approx(1000.0)
    assert _as_float("2.5e-2") == pytest.approx(0.025)


def test_as_float_with_negative_values() -> None:
    """Test _as_float with negative values."""
    assert _as_float(-10.5) == -10.5
    assert _as_float("-3.14") == -3.14


def test_as_float_with_infinity() -> None:
    """Test _as_float with infinity values."""
    assert _as_float(float("inf")) == float("inf")
    assert _as_float(float("-inf")) == float("-inf")


def test_as_str_int_map_with_empty_dict() -> None:
    """Test _as_str_int_map with empty dictionary."""
    assert _as_str_int_map({}) == {}


def test_as_str_int_map_with_mixed_keys() -> None:
    """Test _as_str_int_map filters non-string keys correctly."""
    src = {
        "valid": 10,
        123: 20,
        None: 30,
        ("tuple",): 40,
        "another": "15",
    }
    out = _as_str_int_map(src)
    assert out == {"valid": 10, "another": 15}


def test_as_str_int_map_with_none_values() -> None:
    """Test _as_str_int_map converts None values to 0."""
    src = {"key1": None, "key2": "bad", "key3": 5}
    out = _as_str_int_map(src)
    assert out == {"key1": 0, "key2": 0, "key3": 5}


def test_as_top_relationships_empty_list() -> None:
    """Test _as_top_relationships with empty list."""
    assert _as_top_relationships([]) == []


def test_as_top_relationships_with_negative_strength() -> None:
    """Test _as_top_relationships preserves negative strength values."""
    src = [("A", "B", "inverse", -0.5)]
    out = _as_top_relationships(src)
    assert out == [("A", "B", "inverse", -0.5)]


def test_as_top_relationships_with_none_in_tuple() -> None:
    """Test _as_top_relationships filters tuples with None values."""
    src = [
        (None, "B", "rel", 0.5),
        ("A", None, "rel", 0.5),
        ("A", "B", None, 0.5),
    ]
    out = _as_top_relationships(src)
    # All should be filtered out because first 3 elements must be strings
    assert out == []


def test_as_top_relationships_with_zero_strength() -> None:
    """Test _as_top_relationships with zero strength values."""
    src = [("A", "B", "weak", 0.0), ("C", "D", "none", 0)]
    out = _as_top_relationships(src)
    assert out == [("A", "B", "weak", 0.0), ("C", "D", "none", 0.0)]


def test_as_top_relationships_with_large_strength() -> None:
    """Test _as_top_relationships with large strength values."""
    src = [("A", "B", "strong", 1000.5), ("C", "D", "max", 1e10)]
    out = _as_top_relationships(src)
    assert out == [("A", "B", "strong", 1000.5), ("C", "D", "max", 1e10)]


def test_as_int_with_whitespace_string() -> None:
    """Test _as_int with string containing whitespace."""
    assert _as_int("  42  ") == 42
    assert _as_int("\t10\n") == 10


def test_as_float_with_whitespace_string() -> None:
    """Test _as_float with string containing whitespace."""
    assert abs(_as_float("  3.14  ") - 3.14) < 1e-9
    assert abs(_as_float("\n2.5\t") - 2.5) < 1e-9
