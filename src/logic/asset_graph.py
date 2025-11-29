from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


class AssetRelationshipGraph:
    """Minimal interface used by visualization code.

    Attributes:
        relationships: Dict[source_id, List[(target_id, rel_type, strength)]]
    """

    def __init__(self) -> None:
        self.relationships: Dict[str, List[Tuple[str, str, float]]] = {}

    def get_3d_visualization_data_enhanced(self) -> Tuple[np.ndarray, List[str], List[str], List[str]]:
        """Return positions, asset_ids, colors, hover_texts for visualization.

        This minimal implementation lays out nodes on a circle when relationships exist,
        and returns a single placeholder node otherwise. It is compatible with the
        expectations of src/visualizations/graph_visuals.py.
        """
        # Gather all asset IDs from the relationships mapping
        all_ids = set(self.relationships.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)

        if not all_ids:
            positions = np.zeros((1, 3))
            return positions, ["A"], ["#888888"], ["Asset A"]

        asset_ids = sorted(all_ids)
        n = len(asset_ids)
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        positions = np.stack([np.cos(theta), np.sin(theta), np.zeros_like(theta)], axis=1)
        colors = ["#4ECDC4"] * n
        hover = [f"Asset: {aid}" for aid in asset_ids]
        return positions, asset_ids, colors, hover

