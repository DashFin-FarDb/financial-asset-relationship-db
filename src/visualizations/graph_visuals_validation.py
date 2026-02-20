from typing import Dict, List, Optional, Set

import numpy as np


def _validate_positions_array(positions: np.ndarray) -> None:
    if not isinstance(positions, np.ndarray):
        raise ValueError(
            f"positions must be a numpy array, got {type(positions).__name__}"
        )
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(f"positions must have shape (n, 3), got {positions.shape}")
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(
            f"positions must contain numeric values, got dtype {positions.dtype}"
        )
    if not np.isfinite(positions).all():
        nan_count = int(np.isnan(positions).sum())
        inf_count = int(np.isinf(positions).sum())
        raise ValueError(
            f"positions must contain finite values. "
            f"Found {nan_count} NaN and {inf_count} Inf"
        )


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(
            f"asset_ids must be a list or tuple, got {type(asset_ids).__name__}"
        )
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            f"colors must be a list/tuple of length {expected_length}, "
            f"got {type(colors).__name__} with length {colors_len}"
        )
    if not all(isinstance(c, str) and c for c in colors):
        raise ValueError("colors must contain non-empty strings")


def _validate_hover_texts_list(hover_texts: List[str], expected_length: int) -> None:
    if not isinstance(hover_texts, (list, tuple)) or len(hover_texts) != expected_length:
        raise ValueError(
            f"hover_texts must be a list/tuple of length {expected_length}"
        )
    if not all(isinstance(h, str) and h for h in hover_texts):
        raise ValueError("hover_texts must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
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
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)
    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(
            f"positions length ({positions.shape[0]}) must match asset_ids length ({n})"
        )
    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    if not isinstance(filter_params, dict):
        raise TypeError(
            f"filter_params must be a dictionary, got {type(filter_params).__name__}"
        )
    invalid = [name for name, val in filter_params.items() if not isinstance(val, bool)]
    if invalid:
        raise TypeError(
            f"The following parameters must be boolean values: {', '.join(invalid)}"
        )


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    if relationship_filters is None:
        return
    if not isinstance(relationship_filters, dict):
        raise TypeError(
            f"relationship_filters must be a dictionary or None, "
            f"got {type(relationship_filters).__name__}"
        )
    invalid_values = [
        k for k, v in relationship_filters.items() if not isinstance(v, bool)
    ]
    if invalid_values:
        raise ValueError(
            f"relationship_filters must contain only boolean values. "
            f"Invalid keys: {', '.join(invalid_values)}"
        )
    invalid_keys = [k for k in relationship_filters if not isinstance(k, str)]
    if invalid_keys:
        raise ValueError(
            f"relationship_filters keys must be strings. Invalid keys: {invalid_keys}"
        )
