from typing import Dict, List, Optional

import numpy as np
import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_constants import REL_TYPE_COLORS
from src.visualizations.graph_visuals_data import (
    _build_asset_id_index,
    _build_edge_coordinates_optimized,
    _build_hover_texts,
    _build_relationship_index,
    _collect_and_group_relationships,
)
from src.visualizations.graph_visuals_validation import _validate_visualization_data


def _get_line_style(rel_type: str, is_bidirectional: bool) -> dict:
    return dict(
        color=REL_TYPE_COLORS[rel_type],
        width=4 if is_bidirectional else 2,
        dash="solid" if is_bidirectional else "dash",
    )


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    base = rel_type.replace("_", " ").title()
    return base + (" (↔)" if is_bidirectional else " (→)")


def _create_trace_for_group(
    rel_type: str,
    is_bidirectional: bool,
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """
    Create a 3D line trace representing all relationships of a given type and directionality.

    Parameters:
        rel_type (str): Relationship type key used to style and group the trace.
        is_bidirectional (bool): Whether the relationships are bidirectional (affects line style and name).
        relationships (List[dict]): Sequence of relationship records belonging to this group.
        positions (np.ndarray): Array of asset 3D coordinates with shape (n, 3).
        asset_id_index (Dict[str, int]): Mapping from asset ID to index into `positions`.

    Returns:
        go.Scatter3d: A Plotly 3D line trace with coordinates for each edge, hover texts, styling, name, and legend grouping.
    """
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(
        relationships, positions, asset_id_index
    )
    hover_texts = _build_hover_texts(relationships, rel_type, is_bidirectional)
    return go.Scatter3d(
        x=edges_x,
        y=edges_y,
        z=edges_z,
        mode="lines",
        line=_get_line_style(rel_type, is_bidirectional),
        hovertext=hover_texts,
        hoverinfo="text",
        name=_format_trace_name(rel_type, is_bidirectional),
        visible=True,
        legendgroup=rel_type,
    )


def _create_node_trace(
    positions: np.ndarray,
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> go.Scatter3d:
    """Create node trace for 3D visualization. Validates all inputs before rendering."""
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)
    if len(asset_ids) == 0:
        raise ValueError("Cannot create node trace with empty inputs")
    return go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers+text",
        marker=dict(
            size=15,
            color=colors,
            opacity=0.9,
            line=dict(color="rgba(0,0,0,0.8)", width=2),
            symbol="circle",
        ),
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont=dict(size=12, color="black"),
        name="Assets",
        visible=True,
    )


def _create_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> List[go.Scatter3d]:
    """
    Create Plotly 3D traces grouped by relationship type and directionality.

    Collects graph relationships for the provided asset_ids, groups them by (relationship type, is_bidirectional), and returns one go.Scatter3d trace per non-empty group suitable for batch addition to a figure.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to visualize.
        positions (np.ndarray): Array of node positions with shape (n, 3), where n equals len(asset_ids).
        asset_ids (List[str]): Ordered list of asset IDs corresponding to rows in `positions`.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean indicating whether that type should be included; if `None`, all relationship types are considered.

    Returns:
        List[go.Scatter3d]: A list of 3D Scatter traces, one per non-empty (relationship type, directionality) group.

    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph instance.
        ValueError: If `graph.relationships` is missing or not a dict.
        ValueError: If `positions` is not a numpy array.
        ValueError: If `len(positions)` does not equal `len(asset_ids)`.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("graph must be an AssetRelationshipGraph instance")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("graph must have a relationships dictionary")
    if not isinstance(positions, np.ndarray):
        raise ValueError("positions must be a numpy array")
    if len(positions) != len(asset_ids):
        raise ValueError("positions array length must match asset_ids length")

    asset_id_index = _build_asset_id_index(asset_ids)
    relationship_groups = _collect_and_group_relationships(
        graph, asset_ids, relationship_filters
    )

    return [
        _create_trace_for_group(
            rel_type, is_bidirectional, rels, positions, asset_id_index
        )
        for (rel_type, is_bidirectional), rels in relationship_groups.items()
        if rels
    ]


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> List[go.Scatter3d]:
    """
    Create diamond-shaped markers positioned at 70% along each unidirectional relationship edge.

    Only relationships that do not have a reverse counterpart with the same type are considered; if none exist, an empty list is returned.

    Returns:
        List[go.Scatter3d]: A list containing a single Scatter3d trace with diamond markers placed at the computed arrow positions and corresponding hover texts, or an empty list if there are no unidirectional edges.

    Raises:
        TypeError: If `graph` is not an instance of AssetRelationshipGraph.
        ValueError: If `graph` lacks a `relationships` dictionary, if `positions` or `asset_ids` are None, if their lengths differ, if `positions` does not have shape (n, 3) or contains non-finite/non-numeric values, or if `asset_ids` contains empty/non-string entries.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("graph must have a relationships dictionary")
    if positions is None or asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    if len(positions) != len(asset_ids):
        raise ValueError("positions and asset_ids must have the same length")

    if not isinstance(positions, np.ndarray):
        positions = np.asarray(positions)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")
    if not isinstance(asset_ids, (list, tuple)):
        asset_ids = list(asset_ids)
    if not np.issubdtype(positions.dtype, np.number):
        try:
            positions = positions.astype(float)
        except Exception as exc:
            raise ValueError("Invalid positions: values must be numeric") from exc
    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")
    if not all(isinstance(a, str) and a for a in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")

    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: List[int] = []
    target_indices: List[int] = []
    hover_texts: List[str] = []

    for (source_id, target_id, rel_type), _ in relationship_index.items():
        if (target_id, source_id, rel_type) not in relationship_index:
            source_indices.append(asset_id_index[source_id])
            target_indices.append(asset_id_index[target_id])
            hover_texts.append(
                f"Direction: {source_id} → {target_id}<br>Type: {rel_type}"
            )

    if not source_indices:
        return []

    src_arr = np.asarray(source_indices, dtype=int)
    tgt_arr = np.asarray(target_indices, dtype=int)
    arrow_positions = positions[src_arr] + 0.7 * (
        positions[tgt_arr] - positions[src_arr]
    )

    return [
        go.Scatter3d(
            x=arrow_positions[:, 0].tolist(),
            y=arrow_positions[:, 1].tolist(),
            z=arrow_positions[:, 2].tolist(),
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=8,
                color="rgba(255, 0, 0, 0.8)",
                line=dict(color="red", width=1),
            ),
            hovertext=hover_texts,
            hoverinfo="text",
            name="Direction Arrows",
            visible=True,
            showlegend=False,
        )
    ]
