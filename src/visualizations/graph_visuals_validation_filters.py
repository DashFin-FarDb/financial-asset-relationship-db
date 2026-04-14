"""Filter validation helpers for graph visualizations."""

from typing import Dict, Optional


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    """Validate that filter_params is a dictionary with boolean values."""
    if not isinstance(filter_params, dict):
        raise TypeError(f"filter_params must be a dictionary, got {type(filter_params).__name__}")
    invalid = [name for name, value in filter_params.items() if not isinstance(value, bool)]
    if invalid:
        raise TypeError(f"The following parameters must be boolean values: {', '.join(invalid)}")


def _ensure_relationship_filters_dict(relationship_filters: object) -> Dict[str, bool]:
    """Return relationship_filters as dict or raise a type error."""
    if isinstance(relationship_filters, dict):
        return relationship_filters
    actual_type = type(relationship_filters).__name__
    raise TypeError(f"relationship_filters must be a dictionary or None, got {actual_type}")


def _get_invalid_value_keys(relationship_filters: Dict[str, bool]) -> list[str]:
    """Return keys whose values are not booleans."""
    return [key for key, value in relationship_filters.items() if not isinstance(value, bool)]


def _get_invalid_key_types(relationship_filters: Dict[str, bool]) -> list[object]:
    """Return keys that are not strings."""
    return [key for key in relationship_filters if not isinstance(key, str)]


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    """Validate relationship_filters shape and key/value types."""
    if relationship_filters is None:
        return

    filters_dict = _ensure_relationship_filters_dict(relationship_filters)
    invalid_values = _get_invalid_value_keys(filters_dict)
    if invalid_values:
        raise ValueError(
            "relationship_filters must contain only boolean values. " f"Invalid keys: {', '.join(invalid_values)}"
        )
    invalid_keys = _get_invalid_key_types(filters_dict)
    if invalid_keys:
        raise ValueError(f"relationship_filters keys must be strings. Invalid keys: {invalid_keys}")
