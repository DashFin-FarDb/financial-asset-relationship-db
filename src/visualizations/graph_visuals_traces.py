"""Helpers to build Plotly Scatter3d traces for asset-graph visuals."""

from typing import Dict, List, Optional

import numpy as np
import plotly.graph_objects as go  # type: ignore[import-untyped]

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_constants import REL_TYPE_COLORS
from src.visualizations.graph_visuals_data import (
    _build_asset_id_index,
    _build_edge_coordinates_optimized,
    _build_hover_texts,
    _build_relationship_index,
    _collect_and_group_relationships,
)
from src.visualizations.graph_visuals_validation import (
    _validate_visualization_data,
)

RELATIONSHIPS_DICT_ERROR = "graph must have a relationships dictionary"


def _get_line_style(rel_type: str, is_bidirectional: bool) -> dict:
    """
    Builds a Plotly line style mapping for a relationship type and its directionality.
    
    Returns:
        dict: Mapping with keys:
            - color (str): Color from REL_TYPE_COLORS for the given relationship type.
            - width (int): 4 if is_bidirectional is True, 2 otherwise.
            - dash (str): "solid" if is_bidirectional is True, "dash" otherwise.
    """
    return {
        "color": REL_TYPE_COLORS[rel_type],
        "width": 4 if is_bidirectional else 2,
        "dash": "solid" if is_bidirectional else "dash",
    }


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """
    Format a human-friendly relationship trace name and append a direction marker.

    Parameters:
        rel_type (str): Relationship type identifier; underscores are replaced with spaces and words are title-cased.
        is_bidirectional (bool): If true, appends " (↔)"; otherwise appends " (→)".

    Returns:
        str: Formatted trace name with a direction marker.
    """
    base = rel_type.replace("_", " ").title()
    return base + (" (↔)" if is_bidirectional else " (→)")


def _create_trace_for_group(
    relationship_key: tuple[str, bool],
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """
    Builds a Plotly Scatter3d trace for a group of relationships that share the same type and direction.

    Parameters:
        relationship_key (tuple[str, bool]): A tuple (rel_type, is_bidirectional) where `rel_type` is the relationship type string and `is_bidirectional` indicates whether the relationship is bidirectional.
        relationships (List[dict]): List of relationship records belonging to the group; each record provides source/target asset identifiers and any metadata used for hover text.
        positions (np.ndarray): Array of node coordinates with shape (n, 3); indices correspond to asset positions.
        asset_id_index (Dict[str, int]): Mapping from asset ID to its row index in `positions`.

    Returns:
        go.Scatter3d: A configured Scatter3d trace containing line segments for the group's edges, hover texts, line styling, and legend grouping.
    """
    rel_type, is_bidirectional = relationship_key
    edges_x, edges_y, edges_z = _build_edge_coordinates_optimized(
        relationships,
        positions,
        asset_id_index,
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
    """
    Builds a Plotly Scatter3d trace representing asset nodes for a 3D graph visualization.

    Parameters:
        positions (np.ndarray): Array of shape (n, 3) with x, y, z coordinates for each asset.
        asset_ids (List[str]): Sequence of asset identifiers used as text labels.
        colors (List[str]): Per-node marker colors (one color per asset).
        hover_texts (List[str]): Per-node hover text entries.

    Returns:
        go.Scatter3d: A configured Scatter3d trace with markers, text labels, and hover text for the provided assets.

    Raises:
        ValueError: If `asset_ids` is empty.
    """
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)
    if len(asset_ids) == 0:
        raise ValueError("Cannot create node trace with empty inputs")
    return go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers+text",
        marker={
            "size": 15,
            "color": colors,
            "opacity": 0.9,
            "line": {"color": "rgba(0,0,0,0.8)", "width": 2},
            "symbol": "circle",
        },
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont={"size": 12, "color": "black"},
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
    Builds Plotly Scatter3d traces for each relationship type and direction group present in the graph.
    
    Parameters:
        relationship_filters (Optional[Dict[str, bool]]): Mapping of relationship type to a boolean indicating whether
            that relationship type should be included; when omitted, all relationship types are considered.
    
    Returns:
        List[go.Scatter3d]: One scatter trace per relationship type/direction group that contains relationships.
    """
    _validate_relationship_trace_inputs(graph, positions, asset_ids)

    asset_id_index = _build_asset_id_index(asset_ids)
    relationship_groups = _collect_and_group_relationships(graph, asset_ids, relationship_filters)

    return [
        _create_trace_for_group(
            (rel_type, is_bidirectional),
            rels,
            positions,
            asset_id_index,
        )
        for (rel_type, is_bidirectional), rels in relationship_groups.items()
        if rels
    ]


def _validate_relationship_trace_inputs(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Validate inputs for constructing relationship traces.

    Parameters:
        graph (AssetRelationshipGraph): Graph object that must be an AssetRelationshipGraph and must contain a `relationships` dictionary.
        positions (np.ndarray): NumPy array of node coordinates with one row per asset.
        asset_ids (List[str]): Sequence of asset identifier strings whose length must equal the number of rows in `positions`.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph.
        ValueError: If `graph.relationships` is missing or not a dict, if `positions` is not a NumPy array, or if `len(positions) != len(asset_ids)`.
    """
    _validate_relationship_graph(graph)
    _validate_positions_array(positions)
    _validate_positions_match_asset_ids(positions, asset_ids)


def _validate_relationship_graph(graph: AssetRelationshipGraph) -> None:
    """
    Validate that `graph` is an AssetRelationshipGraph and exposes a `relationships` dictionary.
    
    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph instance ("graph must be an AssetRelationshipGraph instance").
        ValueError: If `graph.relationships` is missing or is not a `dict` (RELATIONSHIPS_DICT_ERROR).
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("graph must be an AssetRelationshipGraph instance")
    if not hasattr(graph, "relationships"):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)
    if not isinstance(graph.relationships, dict):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)


def _validate_positions_array(positions: np.ndarray) -> None:
    """
    Validate that `positions` is a NumPy ndarray.
    
    Raises:
        ValueError: If `positions` is not a `numpy.ndarray`.
    """
    if not isinstance(positions, np.ndarray):
        raise ValueError("positions must be a numpy array")


def _validate_positions_match_asset_ids(
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """
    Ensure the number of position entries equals the number of asset IDs.

    Parameters:
        positions (np.ndarray): Array of positions where each row represents an asset's coordinates.
        asset_ids (List[str]): List of asset identifier strings.

    Raises:
        ValueError: If the length of `positions` does not equal the length of `asset_ids`.
    """
    if len(positions) != len(asset_ids):
        raise ValueError("positions array length must match asset_ids length")


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """
    Create diamond markers placed at 70% along each unidirectional relationship edge.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to render arrows for.
        positions (np.ndarray): 2D array of 3D coordinates aligned with asset_ids.
        asset_ids (list[str]): Ordered list of asset IDs corresponding to rows in `positions`.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping of relationship type to a boolean
            visibility flag; arrows are rendered only for relationship types whose flag is True when provided.

    Returns:
        list[go.Scatter3d]: A list of Plotly Scatter3d traces representing diamond-shaped arrow markers
        for unidirectional relationships that pass the optional filters.
    """
    (
        positions_arr,
        asset_ids_norm,
    ) = _validate_and_prepare_directional_arrows_inputs(
        graph,
        positions,
        asset_ids,
    )
    return _create_directional_arrows_traces(
        graph,
        positions_arr,
        asset_ids_norm,
        relationship_filters,
    )


def _validate_and_prepare_directional_arrows_inputs(
    graph: AssetRelationshipGraph,
    positions,
    asset_ids,
) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize inputs for directional arrow trace creation.

    Ensures `graph` is an AssetRelationshipGraph with a relationships dictionary, converts `positions` to a numeric, finite NumPy array of shape (n, 3), and validates `asset_ids` as a sequence of n non-empty strings.

    Parameters:
        graph (AssetRelationshipGraph): Graph object containing a `relationships` dict.
        positions (array-like): Positions convertible to an (n, 3) numeric ndarray.
        asset_ids (Sequence[str] | None): Sequence of asset ID strings whose length must match `positions`.

    Returns:
        tuple[np.ndarray, list[str]]: `positions_array` — an (n, 3) finite numeric ndarray; `asset_ids_list` — a list of n non-empty asset ID strings.
    """
    _validate_graph(graph)
    positions_arr = _prepare_positions(positions)
    positions_arr, asset_ids_list = _prepare_asset_ids(
        asset_ids,
        positions_arr,
    )
    return positions_arr, asset_ids_list


def _validate_graph(graph: AssetRelationshipGraph):
    """
    Ensure the provided graph is an AssetRelationshipGraph that exposes a relationships dictionary.
    
    Parameters:
        graph (AssetRelationshipGraph): The graph to validate.
    
    Raises:
        TypeError: If `graph` is not an instance of AssetRelationshipGraph.
        ValueError: If `graph.relationships` is missing or is not a dict (message: "graph must have a relationships dictionary").
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError("Expected graph to be an instance of AssetRelationshipGraph")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)


def _prepare_positions(positions) -> np.ndarray:
    """
    Normalize the input positions into a NumPy array suitable for downstream validation.

    Parameters:
        positions: Array-like sequence of shape (n, 3) or convertible to such; must not be None.

    Returns:
        np.ndarray: The input converted to a NumPy array.

    Raises:
        ValueError: If `positions` is None.
    """
    if positions is None:
        raise ValueError("positions and asset_ids must not be None")
    return np.asarray(positions)


def _prepare_asset_ids(
    asset_ids,
    positions_arr: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize asset IDs together with their positions and return cleaned outputs.
    
    Validates that `asset_ids` is a sequence of non-empty strings whose length matches the number of rows in `positions_arr`, and ensures `positions_arr` is a numeric, finite array with shape (n, 3).
    
    Parameters:
        asset_ids: Sequence of asset identifier strings to validate.
        positions_arr (np.ndarray): Array of positions with one row per asset.
    
    Returns:
        tuple[np.ndarray, list[str]]: A validated and normalized positions array with shape (n, 3) and a list of validated asset ID strings.
    """
    asset_ids_list = _validate_asset_ids(asset_ids, positions_arr.shape[0])
    positions_clean = _validate_and_normalize_positions(positions_arr)
    return positions_clean, asset_ids_list


def _validate_asset_ids(asset_ids, expected_len: int) -> list[str]:
    """
    Validate and return a normalized list of asset IDs matching an expected length.
    
    Checks that `asset_ids` is provided, is a list or tuple, has length `expected_len`, and contains only non-empty strings. Returns a new list containing the validated asset IDs.
    
    Parameters:
        asset_ids (list|tuple[str]): Sequence of asset ID strings to validate.
        expected_len (int): Required number of asset IDs.
    
    Returns:
        list[str]: The validated asset IDs as a list.
    
    Raises:
        ValueError: If `asset_ids` is None, its length does not equal `expected_len`, or any entry is an empty string.
        TypeError: If `asset_ids` is not a list or tuple of strings.
    """
    _ensure_asset_ids_present(asset_ids)
    _ensure_asset_ids_sequence(asset_ids)
    _ensure_asset_ids_length(asset_ids, expected_len)
    _ensure_asset_ids_non_empty_strings(asset_ids)
    return list(asset_ids)


def _ensure_asset_ids_present(asset_ids) -> None:
    """
    Validate that an asset_ids sequence is provided.
    
    Parameters:
        asset_ids: Sequence of asset identifier strings or None.
    
    Raises:
        ValueError: If `asset_ids` is None; message is "positions and asset_ids must not be None".
    """
    if asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")


def _ensure_asset_ids_sequence(asset_ids) -> None:
    """
    Validate that `asset_ids` is a sequence of asset identifier strings.
    
    Parameters:
        asset_ids (list|tuple): Expected to be a list or tuple of strings.
    
    Raises:
        TypeError: If `asset_ids` is not a list or tuple.
    """
    if not isinstance(asset_ids, (list, tuple)):
        raise TypeError("asset_ids must be a list or tuple of strings")


def _ensure_asset_ids_length(asset_ids, expected_len: int) -> None:
    """
    Ensure `asset_ids` has exactly `expected_len` entries.
    
    Parameters:
        asset_ids (Sequence): Sequence of asset identifier values.
        expected_len (int): Required number of asset IDs.
    
    Raises:
        ValueError: If the length of `asset_ids` does not equal `expected_len` (message: "positions and asset_ids must have the same length").
    """
    if len(asset_ids) != expected_len:
        raise ValueError("positions and asset_ids must have the same length")


def _ensure_asset_ids_non_empty_strings(asset_ids) -> None:
    """
    Ensure each element of `asset_ids` is a non-empty string.
    
    Parameters:
        asset_ids (Sequence): Sequence of asset identifier values to validate.
    
    Raises:
        ValueError: If any element is not a `str` or is an empty string with message
                    "asset_ids must contain non-empty strings".
    """
    if any((not isinstance(aid, str) or not aid) for aid in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_and_normalize_positions(positions: np.ndarray) -> np.ndarray:
    """
    Ensure `positions` is a finite numeric NumPy array with shape (n, 3).

    Validates that `positions` has two dimensions with three coordinates per entry, coerces to a numeric (floating) dtype if necessary, and verifies all values are finite.

    Raises:
        ValueError: If `positions` does not have shape (n, 3) or contains non-finite/non-numeric values.

    Returns:
        np.ndarray: A NumPy array of shape (n, 3) with a floating numeric dtype and all finite values.
    """
    _ensure_positions_shape(positions)
    numeric_positions = _coerce_positions_to_numeric(positions)
    _ensure_positions_finite(numeric_positions)
    return numeric_positions


def _ensure_positions_shape(positions: np.ndarray) -> None:
    """
    Validate that `positions` is a 2-D NumPy array with shape (n, 3).

    Parameters:
        positions (np.ndarray): Array of position vectors where each row is a 3-component coordinate.

    Raises:
        ValueError: If `positions` is not 2-D or its second dimension is not 3. The exception message is "Invalid positions shape: expected (n, 3)".
    """
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")


def _coerce_positions_to_numeric(positions: np.ndarray) -> np.ndarray:
    """
    Coerce a positions array to a numeric floating-point dtype.

    Returns:
        np.ndarray: The original array if its dtype is already numeric; otherwise a new array cast to float.
    """
    if np.issubdtype(positions.dtype, np.number):
        return positions
    return positions.astype(float)


def _ensure_positions_finite(positions: np.ndarray) -> None:
    """
    Validate that all values in `positions` are finite numbers.
    
    Raises:
        ValueError: If any element of `positions` is not a finite number.
    """
    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")


def _create_directional_arrows_traces(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """
    Create 3D directional arrow traces for relationships that are present in one direction but not the reverse.

    When a relationship from A to B exists and the reverse (B to A) of the same type does not, an arrow marker is placed along the edge at 70% of the distance from source to target. If relationship_filters is provided, a relationship type is included only when its filter value is True. Returns an empty list when no directional arrows are produced.

    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph containing relationship entries.
        positions (np.ndarray): (n, 3) array of vertex coordinates aligned with asset_ids.
        asset_ids (list[str]): Sequence of asset identifiers corresponding to rows in positions.
        relationship_filters (Optional[Dict[str, bool]]): Optional mapping from relationship type to a boolean indicating whether arrows for that type should be created; types missing from the mapping default to included.

    Returns:
        list[go.Scatter3d]: A list containing a single Scatter3d trace of arrow markers positioned along asymmetric edges, or an empty list if no arrows are generated.
    """
    relationship_index = _build_relationship_index(graph, asset_ids)
    asset_id_index = _build_asset_id_index(asset_ids)

    source_indices: list[int] = []
    target_indices: list[int] = []
    hover_texts: list[str] = []

    for (source_id, target_id, rel_type), _ in relationship_index.items():
        # Skip relationship types that the user has hidden via filters.
        if relationship_filters is not None and not relationship_filters.get(rel_type, True):
            continue
        # Only add an arrow if reverse relationship is absent.
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
