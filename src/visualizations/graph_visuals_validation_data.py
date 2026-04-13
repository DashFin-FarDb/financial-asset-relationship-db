"""Data validation helpers for graph visualizations."""

from typing import List, Set

from src.visualizations.graph_visuals_positions import _normalize_positions


def _validate_positions_array(positions: object) -> None:
    """Validate that positions is a finite numeric (n, 3) matrix-like value."""
    _normalize_positions(positions)


def _validate_asset_ids_list(asset_ids: List[str]) -> None:
    """Validate that asset_ids is a list or tuple of non-empty strings."""
    if not isinstance(asset_ids, (list, tuple)):
        raise ValueError(f"asset_ids must be a list or tuple, got {type(asset_ids).__name__}")
    if not all(isinstance(asset_id, str) and asset_id for asset_id in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_colors_list(colors: List[str], expected_length: int) -> None:
    """Validate that colors is a list/tuple of non-empty strings with expected length."""
    if not isinstance(colors, (list, tuple)) or len(colors) != expected_length:
        colors_len = len(colors) if isinstance(colors, (list, tuple)) else "N/A"
        raise ValueError(
            f"colors must be a list/tuple of length {expected_length}, "
            f"got {type(colors).__name__} with length {colors_len}"
        )
    if not all(isinstance(color, str) and color for color in colors):
        raise ValueError("colors must contain non-empty strings")


def _validate_hover_texts_list(hover_texts: List[str], expected_length: int) -> None:
    """Validate that hover_texts is a list/tuple of non-empty strings with expected length."""
    if not isinstance(hover_texts, (list, tuple)) or len(hover_texts) != expected_length:
        raise ValueError(f"hover_texts must be a list/tuple of length {expected_length}")
    if not all(isinstance(hover_text, str) and hover_text for hover_text in hover_texts):
        raise ValueError("hover_texts must contain non-empty strings")


def _validate_asset_ids_uniqueness(asset_ids: List[str]) -> None:
    """Validate asset_ids uniqueness and report duplicate IDs."""
    if len(set(asset_ids)) == len(asset_ids):
        return
    seen: Set[str] = set()
    duplicates: List[str] = []
    for asset_id in asset_ids:
        if asset_id in seen and asset_id not in duplicates:
            duplicates.append(asset_id)
        seen.add(asset_id)
    raise ValueError(f"Duplicate asset_ids detected: {', '.join(duplicates)}")


def _validate_visualization_data(
    positions: object,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> None:
    """Validate coherence between positions, asset ids, colors, and hover texts."""
    _validate_positions_array(positions)
    _validate_asset_ids_list(asset_ids)

    positions_arr = _normalize_positions(positions)
    expected_length = len(asset_ids)
    if len(positions_arr) != expected_length:
        raise ValueError(f"positions length ({len(positions_arr)}) must match asset_ids length ({expected_length})")

    _validate_colors_list(colors, expected_length)
    _validate_hover_texts_list(hover_texts, expected_length)
    _validate_asset_ids_uniqueness(asset_ids)
