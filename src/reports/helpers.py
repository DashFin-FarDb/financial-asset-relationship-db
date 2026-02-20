from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to an int, returning the provided fallback when conversion is not possible.

    Parameters:
        value (Any): The value to coerce to an integer. If `None` or not coercible, the `default` is used.
        default (int): Integer to return when `value` is `None` or cannot be converted.

    Returns:
        int: The coerced integer, or `default` if coercion fails.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Convert a value to a float, returning a fallback when conversion is not possible.

    Parameters:
        value: The input to convert; if None or not convertible to float, the fallback is used.
        default (float): Value to return when conversion fails; defaults to 0.0.

    Returns:
        The converted float, or `default` if `value` is None or cannot be converted to float.
    """
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str_int_map(value: Any) -> dict[str, int]:
    """
    Normalize a mapping-like object into a dict mapping string keys to integers.

    Parameters:
        value (Any): The input to normalize; expected to be a mapping of keys to values.

    Returns:
        dict[str, int]: A dictionary containing only keys that are strings. Values are converted to integers with a fallback of 0 for missing or non-coercible values. Returns an empty dict if `value` is not a mapping.
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
    Normalize input into a list of top-relationship records.

    Parameters:
        value: An iterable of candidate relationships. Each valid item must be a 4-tuple
            (source_id, target_id, type, strength) where the first three elements are strings.
            Non-iterable inputs or items that don't match this contract are ignored.

    Returns:
        list[tuple[str, str, str, float]]: A list of validated tuples with `strength` coerced to
        a float; entries that do not conform to the 4-element (str, str, str, Any) shape are omitted.
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
