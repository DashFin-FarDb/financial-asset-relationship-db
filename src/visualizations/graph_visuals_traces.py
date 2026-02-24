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
    """
    Compute the line style for an edge based on its relationship type and whether it is bidirectional.

    Returns:
        dict: Mapping with keys:
            - `color` (str): Hex or named color for the relationship type.
            - `width` (int): 4 for bidirectional edges, 2 for unidirectional edges.
            - `dash` (str): `"solid"` for bidirectional edges, `"dash"` for unidirectional edges.
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
    """
    Create a Plotly Scatter3d trace representing all edges for a single relationship type and direction.

    Parameters:
        rel_type (str): Relationship type identifier used for styling and legend grouping.
        is_bidirectional (bool): Whether the relationships in this group are bidirectional.
        relationships (List[dict]): Sequence of relationship records (edge objects) to include in the trace.
        positions (np.ndarray): Array of asset 3D positions with shape (n, 3).
        asset_id_index (Dict[str, int]): Mapping from asset ID to row index in `positions`.

    Returns:
        go.Scatter3d: A Scatter3d trace plotting the group edges as 3D lines with hover text, line styling, name, and legend grouping.
    """
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(relationships, positions, asset_id_index)
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
    Create one Plotly Scatter3d trace for each group of relationships that share the same type and directionality.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing a `relationships` dictionary to group.
        positions (np.ndarray): Array of 3D coordinates for assets; length must match `asset_ids`.
        asset_ids (List[str]): Ordered list of asset IDs corresponding to `positions`.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship types to a boolean
                flag indicating whether that type should be included (True) or excluded (False).

    Returns:
        list[go.Scatter3d]: A list of Scatter3d traces, one per (relationship type, is_bidirectional) group
        that contains relationships.

    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph or lacks a `relationships` dict,
        `positions` is not a numpy array, or the length of `positions` does not match `asset_ids`.
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
    relationship_groups = _collect_and_group_relationships(graph, asset_ids, relationship_filters)

    return [
        _create_trace_for_group(rel_type, is_bidirectional, rels, positions, asset_id_index)
        for (rel_type, is_bidirectional), rels in relationship_groups.items()
        if rels
    ]


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
) -> list[go.Scatter3d]:
    """
    Build directional arrow traces as diamond markers placed at 70% along each unidirectional relationship.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing asset relationships.
        positions (np.ndarray): Array of shape (n, 3) with XYZ coordinates for each asset.
        asset_ids (list[str]): Asset ID strings aligned with rows of `positions`.

    Returns:
        list[go.Scatter3d]: A list containing a single Scatter3d trace of diamond markers for all unidirectional edges, or an empty list if no directional arrows are present.
    """
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
    Prepare and validate inputs for creating directional arrow traces.

    Validates that `graph` is a valid AssetRelationshipGraph, converts `positions` to a float numpy array of shape (n, 3) with finite numeric values, and validates `asset_ids` as a list of non-empty strings whose length matches the number of positions.

    Returns:
        tuple[np.ndarray, list[str]]: A tuple containing the normalized positions array (shape (n, 3), dtype float) and the validated list of asset ID strings.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph or `asset_ids` is not a list/tuple of strings.
        ValueError: If `graph` is missing relationships, `positions` is None or has invalid shape/values, or `asset_ids` is empty, contains empty strings, or its length does not match `positions`.
    """
    _validate_graph(graph)
    positions_arr = _prepare_positions(positions)
    positions_arr, asset_ids_list = _prepare_asset_ids(asset_ids, positions_arr)
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
    Convert an array-like of positions to a NumPy array.

    This function converts the provided `positions` to a NumPy array using `np.asarray` without performing shape or finiteness checks.

    Parameters:
        positions: An array-like object of positions (e.g., list, tuple, or numpy array). May be any shape.

    Returns:
        np.ndarray: The input converted to a NumPy array (may be a view of the original data).

    Raises:
        ValueError: If `positions` is None.
    """
    if positions is None:
        raise ValueError("positions and asset_ids must not be None")
    return np.asarray(positions)


def _prepare_asset_ids(asset_ids, positions_arr: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize asset IDs to match the provided positions.

    Ensures `asset_ids` is a list or tuple of non-empty strings whose length equals the number of rows in `positions_arr`.
    Converts and validates `positions_arr` into a float numpy array of shape (n, 3) containing finite numeric values.

    Returns:
        positions_clean (np.ndarray): Normalized (n, 3) float array of positions.
        asset_ids_list (list[str]): List of validated asset ID strings.

    Raises:
        ValueError: If `asset_ids` is None, length does not match `positions_arr`, or `positions_arr` has incorrect shape or contains non-finite values.
        TypeError: If `asset_ids` is not a list or tuple of strings.
    """
    asset_ids_list = _validate_asset_ids(asset_ids, positions_arr.shape[0])
    positions_clean = _validate_and_normalize_positions(positions_arr)
    return positions_clean, asset_ids_list


def _validate_asset_ids(asset_ids, expected_len: int) -> list[str]:
    """
    Validate and normalize a sequence of asset IDs against an expected length.

    Ensures `asset_ids` is a list or tuple of non-empty strings and that its length equals `expected_len`. Returns a new list containing the validated asset ID strings.

    Parameters:
        asset_ids (list[str] | tuple[str]): Sequence of asset ID values to validate.
        expected_len (int): Required number of asset IDs.

    Returns:
        list[str]: A list of validated, non-empty asset ID strings.

    Raises:
        ValueError: If `asset_ids` is None, contains empty or non-string entries, or its length does not equal `expected_len`.
        TypeError: If `asset_ids` is not a list or tuple.
    """
    if asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")
    if not isinstance(asset_ids, (list, tuple)):
        raise TypeError("asset_ids must be a list or tuple of strings")
    if len(asset_ids) != expected_len:
        raise ValueError("positions and asset_ids must have the same length")
    validated = []
    for idx, aid in enumerate(asset_ids):
        if not isinstance(aid, str) or not aid:
            raise ValueError("asset_ids must contain non-empty strings")
        validated.append(aid)
    return validated


def _validate_and_normalize_positions(positions: np.ndarray) -> np.ndarray:
    """
    Validate and normalize position coordinates into a (n, 3) float array.

    Parameters:
        positions (np.ndarray): Array-like of 3D coordinates with shape (n, 3).

    Returns:
        np.ndarray: A float numpy array of shape (n, 3) containing finite numeric values.

    Raises:
        ValueError: If positions does not have shape (n, 3), contains non-numeric values that cannot be converted to float, or contains non-finite values.
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
    Create a Scatter3d trace of diamond markers placed along edges to indicate direction for asymmetric relationships.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing relationships to inspect.
        positions (np.ndarray): Array of shape (n, 3) with 3D coordinates for each asset.
        asset_ids (list[str]): List of asset identifier strings corresponding to positions.

    Returns:
        list[go.Scatter3d]: A one-element list containing a Scatter3d trace with diamond markers positioned at 70% from source toward target for each asymmetric relationship, or an empty list if no asymmetric relationships exist. The trace includes hover text indicating the source → target and relationship type.
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
            hover_texts.append(f"Direction: {source_id} → {target_id}<br>Type: {rel_type}")

    if not source_indices:
        return []

    src_arr = np.asarray(source_indices, dtype=int)
    tgt_arr = np.asarray(target_indices, dtype=int)
    arrow_positions = positions[src_arr] + 0.7 * (positions[tgt_arr] - positions[src_arr])

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
