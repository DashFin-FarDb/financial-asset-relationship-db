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
    """Return line style based on type and directionality.

    Includes color, width, and dash pattern.
    """
    return {
        "color": REL_TYPE_COLORS[rel_type],
        "width": 4 if is_bidirectional else 2,
        "dash": "solid" if is_bidirectional else "dash",
    }


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """Format relationship trace name and direction marker.

    Replaces underscores with spaces and appends arrow marker.
    """
    base = rel_type.replace("_", " ").title()
    return base + (" (↔)" if is_bidirectional else " (→)")


def _create_trace_for_group(
    relationship_key: tuple[str, bool],
    relationships: List[dict],
    positions: np.ndarray,
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """Build one Scatter3d trace for relationships with same type/direction.

    Generates edge coordinates, hover text, and line styling.
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
    """Create validated node trace for 3D visualization."""
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
    """Create one trace per relationship type/direction group."""
    _validate_relationship_trace_inputs(graph, positions, asset_ids)

    asset_id_index = _build_asset_id_index(asset_ids)
    relationship_groups = _collect_and_group_relationships(
        graph, asset_ids, relationship_filters
    )

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
    """Validate required inputs for relationship trace creation."""
    _validate_relationship_graph(graph)
    _validate_positions_array(positions)
    _validate_positions_match_asset_ids(positions, asset_ids)


def _validate_relationship_graph(graph: AssetRelationshipGraph) -> None:
    """Validate relationship graph type and container."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("graph must be an AssetRelationshipGraph instance")
    if not hasattr(graph, "relationships"):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)
    if not isinstance(graph.relationships, dict):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)


def _validate_positions_array(positions: np.ndarray) -> None:
    """Validate positions container type."""
    if not isinstance(positions, np.ndarray):
        raise ValueError("positions must be a numpy array")


def _validate_positions_match_asset_ids(
    positions: np.ndarray,
    asset_ids: List[str],
) -> None:
    """Validate positions count matches asset IDs count."""
    if len(positions) != len(asset_ids):
        raise ValueError("positions array length must match asset_ids length")


def _create_directional_arrows(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """Create diamond markers at 70% along each unidirectional edge.

    Args:
        graph: The asset relationship graph.
        positions: 3-D positions array aligned with asset_ids.
        asset_ids: Assets to include.
        relationship_filters: Optional mapping of relationship type to
            visibility flag.  When provided, arrow markers are only
            rendered for relationship types whose flag is True.
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
    positions_arr, asset_ids_list = _prepare_asset_ids(
        asset_ids,
        positions_arr,
    )
    return positions_arr, asset_ids_list


def _validate_graph(graph: AssetRelationshipGraph):
    """
    Validate that the provided graph is a valid AssetRelationshipGraph.

    Checks type and relationships dictionary presence.

    Raises:
        TypeError: if graph is not an instance of AssetRelationshipGraph.
        ValueError: if graph.relationships is missing or not a dict.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            "Expected graph to be an instance of AssetRelationshipGraph"
        )
    if not hasattr(graph, "relationships") or not isinstance(
        graph.relationships, dict
    ):
        raise ValueError(RELATIONSHIPS_DICT_ERROR)


def _prepare_positions(positions) -> np.ndarray:
    """
    Convert positions into a NumPy array for validation.

    Raises:
        ValueError: if positions is None.
    """
    if positions is None:
        raise ValueError("positions and asset_ids must not be None")
    return np.asarray(positions)


def _prepare_asset_ids(
    asset_ids,
    positions_arr: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """
    Validate and normalize asset IDs corresponding to provided positions.

    Ensures asset IDs are valid and positions are normalized.

    Raises:
        ValueError: if asset_ids is invalid or positions are invalid.
        TypeError: if asset_ids is not a list or tuple of strings.
    """
    asset_ids_list = _validate_asset_ids(asset_ids, positions_arr.shape[0])
    positions_clean = _validate_and_normalize_positions(positions_arr)
    return positions_clean, asset_ids_list


def _validate_asset_ids(asset_ids, expected_len: int) -> list[str]:
    """Validate and normalize a list of asset IDs.

    Ensures asset_ids is a non-None list/tuple of
    non-empty strings matching expected length.

    Raises:
        ValueError: if asset_ids is None, length mismatch,
            or contains invalid IDs.
        TypeError: if asset_ids is not a list or tuple of strings.

    Returns:
        A list of validated asset ID strings.
    """
    _ensure_asset_ids_present(asset_ids)
    _ensure_asset_ids_sequence(asset_ids)
    _ensure_asset_ids_length(asset_ids, expected_len)
    _ensure_asset_ids_non_empty_strings(asset_ids)
    return list(asset_ids)


def _ensure_asset_ids_present(asset_ids) -> None:
    """Ensure asset IDs input is provided."""
    if asset_ids is None:
        raise ValueError("positions and asset_ids must not be None")


def _ensure_asset_ids_sequence(asset_ids) -> None:
    """Ensure asset IDs are a sequence type."""
    if not isinstance(asset_ids, (list, tuple)):
        raise TypeError("asset_ids must be a list or tuple of strings")


def _ensure_asset_ids_length(asset_ids, expected_len: int) -> None:
    """Ensure asset IDs length matches expected value."""
    if len(asset_ids) != expected_len:
        raise ValueError("positions and asset_ids must have the same length")


def _ensure_asset_ids_non_empty_strings(asset_ids) -> None:
    """Ensure each asset ID is a non-empty string."""
    if any((not isinstance(aid, str) or not aid) for aid in asset_ids):
        raise ValueError("asset_ids must contain non-empty strings")


def _validate_and_normalize_positions(positions: np.ndarray) -> np.ndarray:
    """Validate and normalize position coordinates.

    Ensures positions is a finite numeric array of shape (n, 3).

    Raises:
        ValueError: if shape is invalid or values are non-numeric/non-finite.

    Returns:
        A numpy array of shape (n, 3) with float type and finite values.
    """
    _ensure_positions_shape(positions)
    numeric_positions = _coerce_positions_to_numeric(positions)
    _ensure_positions_finite(numeric_positions)
    return numeric_positions


def _ensure_positions_shape(positions: np.ndarray) -> None:
    """Ensure positions has expected 2D shape (n, 3)."""
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("Invalid positions shape: expected (n, 3)")


def _coerce_positions_to_numeric(positions: np.ndarray) -> np.ndarray:
    """Convert positions to numeric dtype when needed."""
    if np.issubdtype(positions.dtype, np.number):
        return positions
    return positions.astype(float)


def _ensure_positions_finite(positions: np.ndarray) -> None:
    """Ensure positions contains only finite numeric values."""
    if not np.isfinite(positions).all():
        raise ValueError("Invalid positions: values must be finite numbers")


def _create_directional_arrows_traces(
    graph: AssetRelationshipGraph,
    positions: np.ndarray,
    asset_ids: list[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> list[go.Scatter3d]:
    """
    Build 3D directional arrow traces for asymmetric relationships.

    Args:
        graph: The asset relationship graph.
        positions: 3-D positions array aligned with asset_ids.
        asset_ids: Assets to include.
        relationship_filters: Optional mapping of relationship type to
            visibility flag.  When provided, only relationship types
            whose flag is True receive arrow markers.

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
        # Skip relationship types that the user has hidden via filters.
        if (
            relationship_filters is not None
            and not relationship_filters.get(rel_type, True)
        ):
            continue
        # Only add an arrow if reverse relationship is absent.
        if (target_id, source_id, rel_type) not in relationship_index:
            source_indices.append(asset_id_index[source_id])
            target_indices.append(asset_id_index[target_id])
            hover_texts.append(
                f"Direction: {source_id} → {target_id}<br>"
                f"Type: {rel_type}"
            )

    if not source_indices:
        return []

    src_arr = np.asarray(source_indices, dtype=int)
    tgt_arr = np.asarray(target_indices, dtype=int)
    arrow_positions = (
        positions[src_arr]
        + 0.7 * (positions[tgt_arr] - positions[src_arr])
    )

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
