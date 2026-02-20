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
    if not positions_3d or not asset_ids:
        return {}
    positions_2d = {}
    for asset_id in asset_ids:
        if asset_id in positions_3d:
            pos_3d = positions_3d[asset_id]
            if hasattr(pos_3d, "__getitem__"):
                positions_2d[asset_id] = (float(pos_3d[0]), float(pos_3d[1]))
    return positions_2d
