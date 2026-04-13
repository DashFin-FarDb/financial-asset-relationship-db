"""Validation helpers for graph visualization inputs."""

from typing import Dict, List, Optional, Set

import numpy as np


def _validate_positions_array(positions: np.ndarray) -> None:
    """
    Validate that `positions` is a NumPy array of 3D coordinates.
    
    Parameters:
        positions (np.ndarray): Array of shape (n, 3) representing n points in 3D space.
    
    Raises:
        ValueError: If `positions` is not a NumPy ndarray, does not have shape (n, 3),
                    has a non-numeric dtype, or contains NaN or infinite values.
    """
    _ensure_ndarray(positions)
    _ensure_positions_shape(positions)
    _ensure_numeric_dtype(positions)
    _ensure_finite_values(positions)


def _ensure_ndarray(positions: np.ndarray) -> None:
    """
    Ensure `positions` is a NumPy ndarray.
    
    Raises:
        ValueError: If `positions` is not an instance of `numpy.ndarray`; the message includes the actual type name.
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError(f"positions must be a numpy array, got {type(positions).__name__}")


def _ensure_positions_shape(positions: np.ndarray) -> None:
    """
    Validate that `positions` is a two-dimensional NumPy array with exactly three columns.

    Parameters:
        positions (np.ndarray): Array representing positions; expected shape is (n, 3).

    Raises:
        ValueError: If `positions` does not have two dimensions or its second dimension is not 3. The error message includes the actual `positions.shape`.
    """
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(f"positions must have shape (n, 3), got {positions.shape}")


def _ensure_numeric_dtype(positions: np.ndarray) -> None:
    """
    Ensure the positions array has a numeric dtype.
    
    Raises:
        ValueError: If the array's dtype is not numeric; message includes the actual dtype.
    """
    if not np.issubdtype(positions.dtype, np.number):
        raise ValueError(f"positions must contain numeric values, got dtype {positions.dtype}")


def _ensure_finite_values(positions: np.ndarray) -> None:
    """
    Validate that all elements of the positions array are finite.
    
    Raises:
        ValueError: If any NaN or infinite values are present. The exception message includes counts of NaN and Inf.
    """
    if np.isfinite(positions).all():
        return
    nan_count = int(np.isnan(positions).sum())
    inf_count = int(np.isinf(positions).sum())
    raise ValueError(f"positions must contain finite values. Found {nan_count} NaN and {inf_count} Inf")


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    """
    Ensure asset_ids is a sequence of non-empty strings.
    
    Parameters:
        asset_ids (list | tuple of str): Sequence of asset identifier strings.
    
    Raises:
        ValueError: If asset_ids is not a list or tuple, or if any element is not a non-empty string.
    """
    if not isinstance(asset_ids, (list, tuple)):
        type_name = type(asset_ids).__name__
        raise ValueError(f"asset_ids must be a list or tuple, got {type_name}")
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """
    Validate that `colors` is a list or tuple of non-empty strings with length equal to `expected_length`.
    
    Parameters:
        colors (List[str]): Sequence of color values; each item must be a non-empty string.
        expected_length (int): Required number of color entries.
    
    Raises:
        ValueError: If `colors` is not a list or tuple of length `expected_length`, or if any entry is not a non-empty string.
    """
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
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
    """
    Validate that hover_texts is a list or tuple of non-empty strings with the specified length.
    
    Parameters:
        hover_texts (List[str]): Sequence of hover text values.
        expected_length (int): Required number of entries in hover_texts.
    """
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
    """
    Validate that hover_texts is a list or tuple.

    Parameters:
        hover_texts (List[str]): Sequence of hover text values; must be a list or tuple.

    Raises:
        ValueError: If hover_texts is not a list or tuple.
    """
    if not isinstance(hover_texts, (list, tuple)):
        raise ValueError("hover_texts must be a list/tuple")


def _ensure_sequence_length(
    sequence: List[str],
    expected_length: int,
    name: str,
) -> None:
    """
    Assert that a sequence has the specified length.
    
    Parameters:
        sequence (List[str]): Sequence to validate (expected to be a list or tuple).
        expected_length (int): Required length for the sequence.
        name (str): Parameter name used in the error message.
    
    Raises:
        ValueError: If len(sequence) != expected_length. Message: "{name} must be a list/tuple of length {expected_length}".
    """
    if len(sequence) != expected_length:
        raise ValueError(f"{name} must be a list/tuple of length {expected_length}")


def _ensure_non_empty_string_values(
    values: List[str],
    name: str,
) -> None:
    """
    Ensure every element in the provided sequence is a non-empty string.

    Parameters:
        values (List[str]): Sequence whose elements must be non-empty strings.
        name (str): Display name used in the error message if validation fails.

    Raises:
        ValueError: If any element in `values` is not a string or is an empty string.
    """
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{name} must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """
    Ensure asset_ids contains only unique strings.
    
    Parameters:
        asset_ids (List[str]): Sequence of asset identifier strings to check.
    
    Raises:
        ValueError: If duplicate asset IDs are found; the exception message lists the duplicated IDs.
    """
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
    """
    Validate that positions, asset IDs, colors, and hover texts are consistent for visualization.

    Performs these checks:
    - positions is a (n, 3) numeric finite NumPy array.
    - asset_ids is a sequence of n non-empty, unique strings.
    - colors is a sequence of n non-empty strings.
    - hover_texts is a sequence of n non-empty strings.
    - positions length (n) matches the lengths of asset_ids, colors, and hover_texts.

    Parameters:
        positions (np.ndarray): Array of 3D coordinates with shape (n, 3).
        asset_ids (List[str]): Sequence of non-empty, unique asset identifier strings; length must equal n.
        colors (List[str]): Sequence of non-empty color strings; length must equal n.
        hover_texts (List[str]): Sequence of non-empty hover text strings; length must equal n.
    """
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)
    n = len(asset_ids)
    if positions.shape[0] != n:
        raise ValueError(f"positions length ({positions.shape[0]}) must match asset_ids length ({n})")
    _validate_colors_list(colors, n)
    _validate_hover_texts_list(hover_texts, n)
    _validate_asset_ids_uniqueness(asset_ids)


def _validate_filter_parameters(filter_params: Dict[str, bool]) -> None:
    """
    Validate that `filter_params` maps parameter names to boolean flags.

    Parameters:
        filter_params (Dict[str, bool]): Mapping from parameter names to boolean values.

    Raises:
        TypeError: If `filter_params` is not a dictionary, or if any value in the mapping is not a `bool`.
    """
    if not isinstance(filter_params, dict):
        raise TypeError(f"filter_params must be a dictionary, got {type(filter_params).__name__}")
    invalid = [name for name, val in filter_params.items() if not isinstance(val, bool)]
    if invalid:
        raise TypeError(f"The following parameters must be boolean values: {', '.join(invalid)}")


def _validate_relationship_filters(
    relationship_filters: Optional[Dict[str, bool]],
) -> None:
    """
    Validate relationship filter mapping.

    If `relationship_filters` is None, no validation is performed. Otherwise verifies that `relationship_filters`
    is a dictionary whose keys are strings and whose values are booleans.

    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping of relationship names to boolean flags or None.

    Raises:
        TypeError: If `relationship_filters` is not a dictionary when provided.
        ValueError: If any key is not a string or any value is not a boolean.
    """
    if relationship_filters is None:
        return
    _ensure_relationship_filters_dict(relationship_filters)
    _ensure_relationship_filter_values(relationship_filters)
    _ensure_relationship_filter_keys(relationship_filters)


def _ensure_relationship_filters_dict(
    relationship_filters: Dict[str, bool],
) -> None:
    """
    Validate that `relationship_filters` is a dictionary.

    Parameters:
        relationship_filters (Dict[str, bool]): The value to validate.

    Raises:
        TypeError: If `relationship_filters` is not a dictionary; the error message includes the actual type name.
    """
    if not isinstance(relationship_filters, dict):
        raise TypeError(f"relationship_filters must be a dictionary or None, got {type(relationship_filters).__name__}")


def _ensure_relationship_filter_values(
    relationship_filters: Dict[str, bool],
) -> None:
    """
    Validate that every value in `relationship_filters` is a boolean.

    Parameters:
        relationship_filters (Dict[str, bool]): Mapping from relationship names to boolean flags.

    Raises:
        ValueError: If any value in `relationship_filters` is not a `bool`; the error message lists the invalid keys.
    """
    invalid_values = [key for key, value in relationship_filters.items() if not isinstance(value, bool)]
    if invalid_values:
        raise ValueError(
            f"relationship_filters must contain only boolean values. Invalid keys: {', '.join(invalid_values)}"
        )


def _ensure_relationship_filter_keys(
    relationship_filters: Dict[str, bool],
) -> None:
    """
    Validate that all keys in `relationship_filters` are strings.

    Parameters:
        relationship_filters (Dict[str, bool]): Mapping of relationship names to booleans; keys must be strings.

    Raises:
        ValueError: If any keys are not strings; the exception message lists the invalid keys.
    """
    invalid_keys = [key for key in relationship_filters if not isinstance(key, str)]
    if invalid_keys:
        raise ValueError(f"relationship_filters keys must be strings. Invalid keys: {invalid_keys}")
