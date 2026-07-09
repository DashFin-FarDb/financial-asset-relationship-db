"""Parser for relationship arguments."""

from typing import Any


def parse_relationship_args(
    relationship_args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[str, float, bool]:
    """
    Normalize flexible add_relationship inputs into a canonical (rel_type, strength, bidirectional) triple.

    Parameters:
        relationship_args (tuple[Any, ...]): Positional args passed to add_relationship; accepts
            either a single tuple (rel_type, strength) or two/three positional values
            (rel_type, strength[, bidirectional]).
        kwargs (dict[str, Any]): Keyword args passed to add_relationship; may include
            `bidirectional` and will be validated for unknown keys.

    Returns:
        rel_type (str): Relationship type coerced to a string.
        strength (float): Relationship strength coerced to a float.
        bidirectional (bool): Whether the relationship should be added bidirectionally.
    """
    (
        rel_type,
        strength,
        bidirectional,
    ) = _dispatch_relationship_parser(
        relationship_args,
        kwargs,
    )
    _ensure_no_unknown_kwargs(kwargs)
    return _finalize_relationship_args(
        rel_type,
        strength,
        bidirectional,
    )


def _dispatch_relationship_parser(
    relationship_args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any, Any, bool]:
    """
    Choose and run the parser corresponding to the provided relationship argument shape.

    Parameters:
        relationship_args (tuple[Any, ...]): Positional arguments forwarded from add_relationship;
            expected shapes are either a single tuple of (rel_type, strength) or two/three
            positional values (rel_type, strength[, bidirectional]).
        kwargs (dict[str, Any]): Keyword arguments forwarded from add_relationship; may contain
            `bidirectional` for the two-argument form or be inspected/consumed by tuple form parsers.

    Returns:
        tuple[Any, Any, bool]: A tuple (rel_type, strength, bidirectional) where `rel_type` is
            the relationship type, `strength` is the relationship strength, and `bidirectional`
            indicates whether the relationship should be added in both directions.

    Raises:
        TypeError: If `relationship_args` does not match any supported shape.
    """
    args_count = len(relationship_args)
    if args_count == 1:
        return _parse_single_relationship_arg(
            relationship_args[0],
            kwargs,
        )
    if args_count in {2, 3}:
        return _parse_positional_relationship(
            relationship_args,
            kwargs,
        )
    raise TypeError(
        "add_relationship expects (rel_type, strength[, bidirectional]) or ((rel_type, strength), [bidirectional])."
    )


def _parse_single_relationship_arg(
    relationship_arg: Any,
    kwargs: dict[str, Any],
) -> tuple[Any, Any, bool]:
    """
    Parse a single positional relationship argument.

    The argument is given as a (rel_type, strength) tuple. This function
    also extracts an optional "bidirectional" flag from kwargs.

    Parameters:
        relationship_arg (Any): A two-item tuple (rel_type, strength).
        kwargs (dict[str, Any]): Keyword arguments; may contain "bidirectional" which will be consumed.

    Returns:
        tuple[Any, Any, bool]: (rel_type, strength, bidirectional)

    Raises:
        TypeError: If `relationship_arg` is not a tuple.
    """
    if not isinstance(relationship_arg, tuple):
        raise TypeError("Single relationship argument must be a tuple of (rel_type, strength).")
    return _parse_tuple_relationship(relationship_arg, kwargs)


def _ensure_no_unknown_kwargs(kwargs: dict[str, Any]) -> None:
    """
    Validate that no unexpected keyword arguments remain after parsing.

    Parameters:
        kwargs (dict[str, Any]): Remaining keyword arguments to check.

    Raises:
        TypeError: If `kwargs` is not empty; the exception message lists the unexpected keys.
    """
    if kwargs:
        unknown = ", ".join(sorted(kwargs.keys()))
        raise TypeError(f"Unexpected keyword arguments: {unknown}")


def _finalize_relationship_args(
    rel_type: Any,
    strength: Any,
    bidirectional: bool,
) -> tuple[str, float, bool]:
    """
    Coerce and validate relationship inputs.

    Returns a normalized (rel_type, strength, bidirectional) triple.

    Parameters:
        rel_type: Relationship type; must be a string identifying the relationship.
        strength: Numeric strength value; will be converted to a float.
        bidirectional: Flag indicating whether the relationship should be added in both directions.

    Returns:
        tuple[str, float, bool]: A tuple containing the relationship type as a `str`,
            the strength as a `float`, and the bidirectional flag as a `bool`.

    Raises:
        TypeError: If `rel_type` is not a `str`.
    """
    if not isinstance(rel_type, str):
        raise TypeError("rel_type must be a string.")
    return rel_type, float(strength), bool(bidirectional)


def _parse_tuple_relationship(
    relationship_tuple: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any, Any, bool]:
    """
    Parse a two-element relationship tuple and extract an explicit bidirectional flag.

    Parameters:
        relationship_tuple (tuple[Any, ...]): A tuple of (rel_type, strength); must have exactly two elements.
        kwargs (dict[str, Any]): May contain a 'bidirectional' key; if present its value is removed from this dict and used.

    Returns:
        tuple[Any, Any, bool]: (rel_type, strength, bidirectional)

    Raises:
        ValueError: If `relationship_tuple` does not contain exactly two elements.
    """
    if len(relationship_tuple) != 2:
        raise ValueError("Relationship tuple must contain (rel_type, strength).")
    rel_type, strength = relationship_tuple
    bidirectional = bool(kwargs.pop("bidirectional", False))
    return rel_type, strength, bidirectional


def _parse_positional_relationship(
    relationship_args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any, Any, bool]:
    """
    Parse legacy positional relationship arguments into a normalized triple: (rel_type, strength, bidirectional).

    Accepts either a 2- or 3-element positional form:
    - With three positional elements, the third element is used as the bidirectional flag.
    - With two positional elements, the `bidirectional` value is taken from `kwargs.pop("bidirectional", False)`.

    Raises:
        TypeError: If `bidirectional` is supplied both positionally (third positional element) and via `kwargs`.

    Returns:
        tuple: `(rel_type, strength, bidirectional)` where `rel_type` is the relationship type,
            `strength` is the relationship strength, and `bidirectional` is `True` if the
            relationship should be added bidirectionally, `False` otherwise.
    """
    rel_type, strength = relationship_args[0], relationship_args[1]
    if len(relationship_args) == 3:
        if "bidirectional" in kwargs:
            raise TypeError("bidirectional specified both positionally and by keyword.")
        return rel_type, strength, bool(relationship_args[2])
    bidirectional_flag = kwargs.pop("bidirectional", False)
    return rel_type, strength, bool(bidirectional_flag)
