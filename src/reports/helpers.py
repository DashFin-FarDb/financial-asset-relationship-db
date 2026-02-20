from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to an integer, falling back to `default` when `value` is None or cannot be converted.

    Parameters:
        default (int): Fallback returned when `value` is None or not convertible to `int`.

    Returns:
        int: `default` if conversion is not possible, otherwise the integer conversion of `value`.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Normalize a value into a float, using a fallback when the value is None or not convertible.

    Parameters:
        default (float): Fallback returned when `value` is `None` or cannot be converted to a float.

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

    Non-string keys are ignored. Each retained value is converted to an integer; if a value is None or cannot be converted, it becomes 0.

    Parameters:
        value (Any): The mapping-like object to normalize. If this is not a Mapping, it is treated as empty.

    Returns:
        dict[str, int]: A dictionary containing only string keys from the input mapped to their integer-converted values.
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

    Each valid entry must be a 4-tuple (source_id, target_id, type, strength). Entries that are not 4-tuples or that do not have string values for source_id, target_id, and type are ignored. The fourth element is coerced to a float, defaulting to 0.0 on failure.

    Returns:
        list[tuple[str, str, str, float]]: A list of (source_id, target_id, type, strength) tuples with `strength` as a float.
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
