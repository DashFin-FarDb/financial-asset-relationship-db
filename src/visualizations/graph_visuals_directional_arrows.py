"""Directional arrow traces for graph visualizations."""

from typing import Dict, Optional, Sequence

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_data import _build_asset_id_index, _build_relationship_index
from src.visualizations.graph_visuals_positions import PositionMatrix, _normalize_positions


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: Sequence[Sequence[float]],
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """Create diamond markers at 70% along each unidirectional edge."""
    positions_arr, asset_ids_norm = _validate_and_prepare_directional_arrows_inputs(
        graph,
        positions,
        asset_ids,
    )
    return _create_directional_arrows_traces(graph, positions_arr, asset_ids_norm, relationship_filters)


def _validate_and_prepare_directional_arrows_inputs(
    graph: AssetRelationshipGraph,
    positions,
    asset_ids,
) -> tuple[PositionMatrix, list[str]]:
    """Validate and normalize inputs for directional arrows."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("graph must have a relationships dictionary")
    positions_arr = _normalize_positions(positions)
    asset_ids_list = _validate_asset_ids(asset_ids, len(positions_arr))
    return positions_arr, asset_ids_list


def _validate_asset_ids(asset_ids, expected_len: int) -> list[str]:
    """Validate and normalize a list of asset IDs."""
    if asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    if not isinstance(asset_ids, (list, tuple)):
        raise TypeError("asset_ids must be a list or tuple of strings")
    if len(asset_ids) != expected_len:
        raise ValueError("positions and asset_ids must have the same length")
    validated = []
    for aid in asset_ids:
        if not isinstance(aid, str) or not aid:
            raise ValueError("asset_ids must contain non-empty strings")
        validated.append(aid)
    return validated


def _create_directional_arrows_traces(
    graph: AssetRelationshipGraph,
    positions: PositionMatrix,
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """Build 3D directional arrow traces for asymmetric relationships."""
    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: list[int] = []
    target_indices: list[int] = []
    hover_texts: list[str] = []

    for (source_id, target_id, rel_type), _ in relationship_index.items():
        if relationship_filters is not None and not relationship_filters.get(rel_type, True):
            continue
        if (target_id, source_id, rel_type) not in relationship_index:
            source_indices.append(asset_id_index[source_id])
            target_indices.append(asset_id_index[target_id])
            hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

    if not source_indices:
        return []

    arrow_positions: PositionMatrix = []
    for src_idx, tgt_idx in zip(source_indices, target_indices, strict=False):
        sx, sy, sz = positions[src_idx]
        tx, ty, tz = positions[tgt_idx]
        arrow_positions.append(
            (
                sx + 0.7 * (tx - sx),
                sy + 0.7 * (ty - sy),
                sz + 0.7 * (tz - sz),
            )
        )

    trace = go.Scatter3d(
        x=[p[0] for p in arrow_positions],
        y=[p[1] for p in arrow_positions],
        z=[p[2] for p in arrow_positions],
        mode="markers",
        marker={
            "symbol": "diamond",
            "size": 8,
            "color": "rgba(255, 0, 0, 0.8)",
            "line": {"color": "red", "width": 1},
        },
        hovertext=hover_texts,
        hoverinfo="text",
        name="Direction Arrows",
        visible=True,
        showlegend=False,
    )
    return [trace]
