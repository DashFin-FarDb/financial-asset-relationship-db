import math
from typing import Dict, List, Tuple


def _create_circular_layout(asset_ids: List[str]) -> Dict[str, Tuple[float, float]]:
    if not asset_ids:
        return {}
    n = len(asset_ids)
    positions = {}
    for i, asset_id in enumerate(asset_ids):
        angle = 2 * math.pi * i / n
        positions[asset_id] = (math.cos(angle), math.sin(angle))
    return positions


def _create_grid_layout(asset_ids: List[str]) -> Dict[str, Tuple[float, float]]:
    """Creates a grid layout for the given asset IDs."""
    if not asset_ids:
        return {}
    cols = int(math.ceil(math.sqrt(len(asset_ids))))
    positions = {}
    for i, asset_id in enumerate(asset_ids):
        positions[asset_id] = (float(i % cols), float(i // cols))
    return positions


def _create_spring_layout_2d(
    positions_3d: Dict[str, Tuple[float, float, float]],
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
    """Create a 2D spring layout from 3D positions.

    This function takes a dictionary of 3D positions and a list of asset IDs,
    returning a new dictionary that contains the corresponding 2D positions for
    each asset ID. It checks if the provided positions_3d and asset_ids are  valid,
    and extracts the first two dimensions of the 3D positions for each  asset ID
    that exists in the positions_3d dictionary.

    Args:
        positions_3d: A dictionary mapping asset IDs to their 3D coordinates.
        asset_ids: A list of asset IDs to retrieve 2D positions for.

    Returns:
        Dict[str, Tuple[float, float]]: A dictionary mapping asset IDs to their
        corresponding 2D coordinates.
    """
    if not positions_3d or not asset_ids:
        return {}
    positions_2d = {}
    for asset_id in asset_ids:
        if asset_id in positions_3d:
            pos_3d = positions_3d[asset_id]
            if hasattr(pos_3d, "__getitem__"):
                positions_2d[asset_id] = (float(pos_3d[0]), float(pos_3d[1]))
    return positions_2d
