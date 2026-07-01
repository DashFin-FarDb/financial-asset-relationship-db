"""Unit tests for the relationship arguments parser."""

import pytest

from src.logic.relationship_parser import parse_relationship_args


def test_parse_single_tuple():
    """Test parsing a single tuple."""
    rel_type, strength, bidir = parse_relationship_args((("test_rel", 0.5),), {})
    assert rel_type == "test_rel"
    assert strength == 0.5
    assert not bidir


def test_parse_single_tuple_with_kwargs():
    """Test parsing a single tuple with a bidirectional kwarg."""
    rel_type, strength, bidir = parse_relationship_args((("test_rel", 0.5),), {"bidirectional": True})
    assert rel_type == "test_rel"
    assert strength == 0.5
    assert bidir


def test_parse_two_positional():
    """Test parsing two positional arguments."""
    rel_type, strength, bidir = parse_relationship_args(("test_rel", 0.5), {})
    assert rel_type == "test_rel"
    assert strength == 0.5
    assert not bidir


def test_parse_two_positional_with_kwargs():
    """Test parsing two positional arguments with a bidirectional kwarg."""
    rel_type, strength, bidir = parse_relationship_args(("test_rel", 0.5), {"bidirectional": True})
    assert rel_type == "test_rel"
    assert strength == 0.5
    assert bidir


def test_parse_three_positional():
    """Test parsing three positional arguments."""
    rel_type, strength, bidir = parse_relationship_args(("test_rel", 0.5, True), {})
    assert rel_type == "test_rel"
    assert strength == 0.5
    assert bidir


def test_parse_invalid_args_length():
    """Test parsing an invalid number of arguments."""
    with pytest.raises(TypeError, match="add_relationship expects"):
        parse_relationship_args((), {})

    with pytest.raises(TypeError, match="add_relationship expects"):
        parse_relationship_args(("test_rel", 0.5, True, "extra"), {})


def test_parse_three_positional_with_kwargs():
    """Test parsing three positional arguments with a bidirectional kwarg."""
    with pytest.raises(TypeError, match="bidirectional specified both positionally and by keyword"):
        parse_relationship_args(("test_rel", 0.5, True), {"bidirectional": True})


def test_parse_invalid_tuple_length():
    """Test parsing an invalid length tuple."""
    with pytest.raises(ValueError, match="Relationship tuple must contain"):
        parse_relationship_args((("test_rel", 0.5, True),), {})

    with pytest.raises(ValueError, match="Relationship tuple must contain"):
        parse_relationship_args((("test_rel",),), {})


def test_parse_unexpected_kwargs():
    """Test parsing with unexpected keyword arguments."""
    with pytest.raises(TypeError, match="Unexpected keyword arguments"):
        parse_relationship_args(("test_rel", 0.5), {"extra_kwarg": "value"})


def test_parse_invalid_rel_type():
    """Test parsing an invalid relationship type."""
    with pytest.raises(TypeError, match="rel_type must be a string"):
        parse_relationship_args(((123, 0.5),), {})
