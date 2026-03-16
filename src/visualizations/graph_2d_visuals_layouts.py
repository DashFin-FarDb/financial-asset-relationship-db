"""
This module provides layout algorithms for positioning assets in 2D
visualizations, including circular, grid, and spring layouts.
"""

import math
from typing import Dict, List, Tuple


def _create_circular_layout(
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
    """
    Map asset IDs to evenly spaced (x, y) coordinates on the unit circle.

    If `asset_ids` is empty, returns an empty dictionary.

    Returns:
        positions (Dict[str, Tuple[float, float]]): Mapping from each
            asset ID to its (x, y) coordinates on the unit circle.
    """
    if not asset_ids:
        return {}
    n = len(asset_ids)
    positions = {}
    for i, asset_id in enumerate(asset_ids):
        angle = 2 * math.pi * i / n
        positions[asset_id] = (math.cos(angle), math.sin(angle))
    return positions


def _create_grid_layout(
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
    """
    Generate grid positions for the given assets arranged in row-major order.
    
    Positions are placed on a grid with cols = ceil(sqrt(n)). For each asset in the input list, the x coordinate is the column index (i % cols) and the y coordinate is the row index (i // cols); both coordinates are returned as floats.
    
    Parameters:
        asset_ids (List[str]): Asset identifiers in the order they should be placed.
    
    Returns:
        Dict[str, Tuple[float, float]]: Mapping from asset ID to its (x, y) grid coordinates, where x is column and y is row.
    """
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
    """
    Convert selected 3D positions to 2D coordinates.
    
    Returns a dictionary mapping each asset ID in `asset_ids` to a tuple of its X and Y
    coordinates taken from `positions_3d`. Asset IDs not present in `positions_3d`
    or whose position value does not support indexing are skipped.
    
    Parameters:
        positions_3d (Dict[str, Tuple[float, float, float]]): Mapping from asset ID to its 3D position.
        asset_ids (List[str]): Asset IDs to include in the resulting 2D layout.
    
    Returns:
        Dict[str, Tuple[float, float]]: Mapping from asset ID to its (x, y) coordinates.
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
