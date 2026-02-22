from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert the input to an integer, using a fallback when conversion is not possible.

    Parameters:
        value (Any): Value to convert to int.
        default (int): Fallback returned when `value` is None or cannot be converted.

    Returns:
        int: The integer conversion of `value`, or `default` if `value` is None or conversion fails.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Convert a value to a float, returning the provided default when conversion is not possible.

    Parameters:
        value: The value to convert to float.
        default (float): Value returned when `value` is None or cannot be converted.

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
    Convert a mapping-like object to a dict with string keys and integer values.

    Parameters:
        value (Any): Input to normalize; non-mapping values result in an empty dict.

    Returns:
        dict[str, int]: Dictionary containing only entries whose keys are strings. Values are coerced to integers, using 0 when conversion fails or the value is None.
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

    Each returned tuple is (source_id, target_id, type, strength) where the first three elements are strings and strength is a float. Items that are not 4-element tuples with string source, target, and type are ignored; if the input is not iterable an empty list is returned.

    Returns:
        list[tuple[str, str, str, float]]: A list of normalized relationship tuples.
    """
    if not isinstance(value, Iterable):
        return []

    out: list[tuple[str, str, str, float]] = []
    for item in value:
        if (
            isinstance(item, tuple)
            and len(item) == 4
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            and isinstance(item[2], str)
        ):
            strength = _as_float(item[3], 0.0)
            out.append((item[0], item[1], item[2], strength))

    return out
