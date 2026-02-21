"""This module contains functions to generate Plotly Scatter3d traces for visualizing asset relationship graphs. It includes utilities for styling relationship lines, formatting trace names, and grouping relationship data into Plotly traces."""

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
    """Return a style dictionary for edges based on relationship type and directionality.

    The style includes color, width, and dash pattern depending on whether the connection is bidirectional.
    """
    return dict(
        color=REL_TYPE_COLORS[rel_type],
        width=4 if is_bidirectional else 2,
        dash="solid" if is_bidirectional else "dash",
    )


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """Format the trace name for a relationship based on its type and if it is bidirectional.

    Replaces underscores with spaces, applies title casing, and appends an arrow symbol to indicate direction.
    """
    base = rel_type.replace("_", " ").title()
    return base + (" (↔)" if is_bidirectional else " (→)")


def _create_trace_for_group(
    rel_type: str,
    is_bidirectional: bool,
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """Build a Plotly Scatter3d trace for a group of relationships of the same type and direction.

    Generates 3D edge coordinates, constructs hover texts, and applies line styling and naming conventions.
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
    """Create one trace per (rel_type, directionality) group for batch addition."""
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
    asset_ids: list[str],
) -> list[go.Scatter3d]:
    """Create diamond markers at 70% along each unidirectional edge."""
    positions_arr, asset_ids_norm = _validate_and_prepare_directional_arrows_inputs(
        graph,
        positions,
        asset_ids,
    )
    return _create_directional_arrows_traces(graph, positions_arr, asset_ids_norm)


def _validate_and_prepare_directional_arrows_inputs(
    graph: AssetRelationshipGraph,
    positions,
    asset_ids,
) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize inputs for directional arrows.

    Ensures:
    - graph is an AssetRelationshipGraph with a relationships dict
    - positions is a numeric (n, 3) array of finite values
    - asset_ids is a list of non-empty strings with same length as positions

    Returns:
        (positions_array, asset_ids_list)
    """
    _validate_graph(graph)
    positions_arr = _prepare_positions(positions)
    asset_ids_list = _prepare_asset_ids(asset_ids, positions_arr)
    return positions_arr, asset_ids_list


def _validate_graph(graph: AssetRelationshipGraph):
    """
    Validate that the provided graph is a valid AssetRelationshipGraph.

    Checks that graph is an instance of AssetRelationshipGraph and has a relationships dictionary.

    Raises:
        TypeError: if graph is not an instance of AssetRelationshipGraph.
        ValueError: if graph.relationships is missing or not a dict.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("graph must have a relationships dictionary")


def _prepare_positions(positions) -> np.ndarray:
    """
    Convert and validate positions into a (n, 3) numpy array of finite numeric values.

    Raises:
        ValueError: if positions is None, not a 2D array of shape (n, 3), or contains non-finite values.
    """
    if positions is None:
        raise ValueError("positions must not be None")
    arr = np.asarray(positions)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("positions must be a 2D array with shape (n, 3)")
    if not np.isfinite(arr).all():
        raise ValueError("positions must contain finite values")
    return arr


def _prepare_asset_ids(
    asset_ids, positions_arr: np.ndarray
) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize asset IDs corresponding to provided positions.

    Ensures asset_ids is a list or tuple of non-empty strings matching the number of positions
    and that positions_arr is a (n, 3) numeric array of finite values.
    Returns the normalized positions array and list of validated asset IDs.

    Raises:
        ValueError: if asset_ids is None or length does not match positions, or if positions_arr
                    has incorrect shape or contains non-finite values.
        TypeError: if asset_ids is not a list or tuple of strings.
    """
    asset_ids_list = _validate_asset_ids(asset_ids, positions_arr.shape[0])
    positions_clean = _validate_and_normalize_positions(positions_arr)
    return positions_clean, asset_ids_list


def _validate_asset_ids(asset_ids, expected_len: int) -> list[str]:
    """Validate and normalize a list of asset IDs.

    Ensures that asset_ids is a non-None list or tuple of non-empty strings matching expected length.

    Raises:
        ValueError: if asset_ids is None, length mismatch, or contains invalid IDs.
        TypeError: if asset_ids is not a list or tuple of strings.

    Returns:
        A list of validated asset ID strings.
    """
    if asset_ids is None:
        raise ValueError("asset_ids must not be None")
    if not isinstance(asset_ids, (list, tuple)):
        raise TypeError("asset_ids must be a list or tuple of strings")
    if len(asset_ids) != expected_len:
        raise ValueError("Length of asset_ids must match number of positions")
    validated = []
    for idx, aid in enumerate(asset_ids):
        if not isinstance(aid, str) or not aid:
            raise ValueError(f"asset_ids[{idx}] must be a non-empty string")
        validated.append(aid)
    return validated


def _validate_and_normalize_positions(positions: np.ndarray) -> np.ndarray:
    """Validate and normalize position coordinates.

    Ensures positions is a 2D numeric array of shape (n, 3) with finite values,
    converting to float if necessary.

    Raises:
        ValueError: if positions shape is invalid, contains non-numeric or non-finite values.

    Returns:
        A numpy array of shape (n, 3) with float type and finite values.
    """
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")
    if not np.issubdtype(positions.dtype, np.number):
        try:
            positions = positions.astype(float)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Invalid positions: values must be numeric") from exc
    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")
    return positions


def _create_directional_arrows_traces(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
) -> list[go.Scatter3d]:
    """
    Build 3D directional arrow traces for asymmetric relationships.

    Returns:
        A list with a single Scatter3d trace, or an empty list if no
        asymmetric relationships exist between the given asset_ids.
    """
    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: list[int] = []
    target_indices: list[int] = []
    hover_texts: list[str] = []

    for (source_id, target_id, rel_type), _ in relationship_index.items():
        # Only add an arrow if there is no reverse relationship of the same type
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

    trace = go.Scatter3d(
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
    return [trace]
