"""Shared helper functions for report data normalization and formatting."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert the input to an integer with a fallback.

    Parameters:
        value (Any): Value to convert to int.
        default (int): Used when `value` is None or cannot be converted.

    Returns:
        int: Converted value, or `default` when conversion fails.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Convert a value to float, with fallback default.

    Parameters:
        value: The value to convert to float.
        default (float): Used when `value` is None or cannot be converted.

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
    Convert mapping-like input to `dict[str, int]`.

    Parameters:
        value (Any): Non-mapping values return an empty dict.

    Returns:
        dict[str, int]: String-key entries only; values are coerced
            to ints with fallback 0.
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

    Each result is `(source_id, target_id, type, strength)`.
    The first three entries must be strings.
    Invalid tuple shapes are ignored.
    Non-iterable input returns an empty list.

    Returns:
        list[tuple[str, str, str, float]]: Normalized relationship tuples.
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
    """Return True when item matches (str, str, str, strength)."""
    if not isinstance(item, tuple):
        return False
    if len(item) != 4:
        return False
    return isinstance(item[0], str) and isinstance(item[1], str) and isinstance(item[2], str)
