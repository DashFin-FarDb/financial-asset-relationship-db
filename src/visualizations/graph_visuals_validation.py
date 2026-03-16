"""Validation helpers for graph visualization inputs."""

from typing import Dict, List, Optional, Set

import numpy as np


def _validate_positions_array(positions: np.ndarray) -> None:
    """Validate positions array type, shape, and finiteness."""
    _ensure_ndarray(positions)
    _ensure_positions_shape(positions)
    _ensure_numeric_dtype(positions)
    _ensure_finite_values(positions)


def _ensure_ndarray(positions: np.ndarray) -> None:
    """Ensure positions is a NumPy array."""
    if not isinstance(positions, np.ndarray):
        raise ValueError(
            f"positions must be a numpy array, got {type(positions).__name__}"
        )


def _ensure_positions_shape(positions: np.ndarray) -> None:
    """Ensure positions has shape (n, 3)."""
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            f"positions must have shape (n, 3), got {positions.shape}"
        )


def _ensure_numeric_dtype(positions: np.ndarray) -> None:
    """Ensure positions array has numeric dtype."""
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(
            "positions must contain numeric values, "
            f"got dtype {positions.dtype}"
        )


def _ensure_finite_values(positions: np.ndarray) -> None:
    """Ensure positions has only finite values."""
    if np.isfinite(positions).all():
        return
    nan_count = int(np.isnan(positions).sum())
    inf_count = int(np.isinf(positions).sum())
    raise ValueError(
        "positions must contain finite values. "
        f"Found {nan_count} NaN and {inf_count} Inf"
    )


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    """Validate asset ID sequence and values."""
    if not isinstance(asset_ids, (list, tuple)):
        type_name = type(asset_ids).__name__
        raise ValueError(
            f"asset_ids must be a list or tuple, got {type_name}"
        )
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """Validate color list shape and values."""
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_len = (
            len(colors)
            if isinstance(colors, (list, tuple))
            else "N/A"
        )
        raise ValueError(
            f"colors must be a list/tuple of length {expected_length}, "
            f"got {type(colors).__name__} with length {colors_len}"
        )
    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("colors must contain non-empty strings")


def _validate_hover_texts_list(
    hover_texts: List[str],
    expected_length: int,
) -> None:
    """Validate hover text list shape and values."""
    _ensure_hover_texts_sequence(hover_texts)
    _ensure_sequence_length(
        sequence=hover_texts,
        expected_length=expected_length,
        name="hover_texts",
    )
    _ensure_non_empty_string_values(
        values=hover_texts,
        name="hover_texts",
    )


def _ensure_hover_texts_sequence(hover_texts: List[str]) -> None:
    """Ensure hover_texts is list/tuple."""
    if not isinstance(hover_texts, (list, tuple)):
        raise ValueError("hover_texts must be a list/tuple")


def _ensure_sequence_length(
    sequence: List[str],
    expected_length: int,
    name: str,
) -> None:
    """Ensure sequence length matches expected length."""
    if len(sequence) != expected_length:
        raise ValueError(
            f"{name} must be a list/tuple of length {expected_length}"
        )


def _ensure_non_empty_string_values(
    values: List[str],
    name: str,
) -> None:
    """Ensure all values are non-empty strings."""
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{name} must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """Validate that asset_ids contains unique values."""
    if len(set(asset_ids)) == len(asset_ids):
        return
    seen: Set[str] = set()
    dups: List[str] = []
    for aid in asset_ids:
        if aid in seen and aid not in dups:
            dups.append(aid)
        seen.add(aid)
    raise ValueError(f"Duplicate asset_ids detected: {', '.join(dups)}")


def _validate_visualization_data(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> None:
    """Validate consistency of positions, IDs, colors, and hover text."""
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)
    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            f"positions length ({positions.shape[0]}) must match "
            f"asset_ids length ({n})"
        )
    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    """Validate that filter_params is a dictionary of booleans."""
    if not isinstance(filter_params, dict):
        raise TypeError(
            "filter_params must be a dictionary, "
            f"got {type(filter_params).__name__}"
        )
    invalid = [
        name
        for name, val in filter_params.items()
        if not isinstance(val, bool)
    ]
    if invalid:
        raise TypeError(
            "The following parameters must be boolean values: "
            f"{', '.join(invalid)}"
        )


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    """Validate relationship filter keys and values."""
    if relationship_filters is None:
        return
    _ensure_relationship_filters_dict(relationship_filters)
    _ensure_relationship_filter_values(relationship_filters)
    _ensure_relationship_filter_keys(relationship_filters)


def _ensure_relationship_filters_dict(
    relationship_filters: Dict[str, bool],
) -> None:
    """Ensure relationship_filters is a dictionary."""
    if not isinstance(relationship_filters, dict):
        raise TypeError(
            "relationship_filters must be a dictionary or None, "
            f"got {type(relationship_filters).__name__}"
        )


def _ensure_relationship_filter_values(
    relationship_filters: Dict[str, bool],
) -> None:
    """Ensure relationship_filters has boolean values."""
    invalid_values = [
        key
        for key, value in relationship_filters.items()
        if not isinstance(value, bool)
    ]
    if invalid_values:
        raise ValueError(
            "relationship_filters must contain only boolean values. "
            f"Invalid keys: {', '.join(invalid_values)}"
        )


def _ensure_relationship_filter_keys(
    relationship_filters: Dict[str, bool],
) -> None:
    """Ensure relationship_filters has string keys."""
    invalid_keys = [
        key
        for key in relationship_filters
        if not isinstance(key, str)
    ]
    if invalid_keys:
        raise ValueError(
            "relationship_filters keys must be strings. "
            f"Invalid keys: {invalid_keys}"
        )
