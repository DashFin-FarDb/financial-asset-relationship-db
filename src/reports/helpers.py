"""Shared helper functions for report data normalization and formatting."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to an integer, returning a fallback when conversion is not possible.

    Parameters:
        value (Any): Value to convert. If None or not convertible, `default` is used.
        default (int): Fallback returned when `value` is None or cannot be converted.

    Returns:
        int: The converted integer, or `default` when conversion fails.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Convert a value to a float, falling back to the provided default when conversion is not possible.

    Parameters:
        value (Any): Input to convert; if None, the `default` is returned.
        default (float): Value returned when `value` is None or cannot be converted to float.

    Returns:
        float: The converted float, or `default` if conversion fails.
    """
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str_int_map(value: Any) -> dict[str, int]:
    """
    Normalize a mapping-like object into a dict with string keys and integer values.

    Parameters:
        value (Any): Input expected to be mapping-like; non-mapping inputs produce an empty dict.

    Returns:
        dict[str, int]: A dictionary containing only entries whose keys are strings. Values are coerced to int; conversion failures default to 0.
    """
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(key, str):
            out[key] = _as_int(raw, 0)

    return out


def _as_top_relationships(
    value: Any,
) -> list[tuple[str, str, str, float]]:
    """
    Normalize an iterable into a list of top-relationship tuples.

    Each tuple is (source_id, target_id, type, strength) where the first three elements are strings and strength is a float coerced from the fourth element. Non-iterable input or items that do not match the expected shape are ignored.

    Returns:
        list[tuple[str, str, str, float]]: List of normalized relationship tuples.
    """
    if not isinstance(value, Iterable):
        return []

    out: list[tuple[str, str, str, float]] = []
    for item in value:
        if _is_top_relationship_item(item):
            strength = _as_float(item[3], 0.0)
            out.append((item[0], item[1], item[2], strength))

    return out


def _is_top_relationship_item(item: Any) -> bool:
    """
    Determine whether an object represents a top-relationship item in the form (source_id, target_id, type, strength).

    Returns:
        bool: `True` if `item` is a 4-tuple whose first three elements are strings, `False` otherwise.
    """
    if not isinstance(item, tuple):
        return False
    if len(item) != 4:
        return False
    return isinstance(item[0], str) and isinstance(item[1], str) and isinstance(item[2], str)
