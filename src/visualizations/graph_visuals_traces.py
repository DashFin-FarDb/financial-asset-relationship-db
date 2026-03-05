"""Build Plotly Scatter3d traces for asset relationship graphs."""

from typing import Dict, List, Optional, Sequence

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_constants import REL_TYPE_COLORS
from src.visualizations.graph_visuals_data import (
    _build_asset_id_index,
    _build_edge_coordinates_optimized,
    _build_hover_texts,
    _collect_and_group_relationships,
)
from src.visualizations.graph_visuals_directional_arrows import _create_directional_arrows
from src.visualizations.graph_visuals_positions import _normalize_positions


def _get_line_style(rel_type: str, is_bidirectional: bool) -> dict:
    """Return a style dictionary for edges based on relationship type and directionality.

    The style includes color, width, and dash pattern depending on whether the connection is bidirectional.
    """
    return {
        "color": REL_TYPE_COLORS[rel_type],
        "width": 4 if is_bidirectional else 2,
        "dash": "solid" if is_bidirectional else "dash",
    }


def _format_trace_name(rel_type: str, is_bidirectional: bool) -> str:
    """Format the trace name for a relationship based on its type and if it is bidirectional.

    Replaces underscores with spaces, applies title casing, and appends an arrow symbol to indicate direction.
    """
    base = rel_type.replace("_", " ").title()
    return base + (" (↔)" if is_bidirectional else " (→)")


def _validate_node_trace_inputs(
    positions_arr: Sequence[Sequence[float]],
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> None:
    """Validate node trace inputs for non-empty and matching lengths."""
    expected_length = len(asset_ids)
    if expected_length == 0:
        raise ValueError("Cannot create node trace with empty inputs")

    length_validations = (
        (len(positions_arr), "positions and asset_ids must have the same length"),
        (len(colors), "colors length must match asset_ids length"),
        (len(hover_texts), "hover_texts length must match asset_ids length"),
    )
    mismatch_error = next(
        (message for length, message in length_validations if length != expected_length),
        None,
    )
    if mismatch_error is not None:
        raise ValueError(mismatch_error)


def _extract_node_coordinates(positions_arr: Sequence[Sequence[float]]) -> tuple[List[float], List[float], List[float]]:
    """Split normalized 3D positions into x/y/z coordinate vectors."""
    x_values: List[float] = []
    y_values: List[float] = []
    z_values: List[float] = []
    for x_coord, y_coord, z_coord in positions_arr:
        x_values.append(x_coord)
        y_values.append(y_coord)
        z_values.append(z_coord)
    return x_values, y_values, z_values


def _build_node_marker(colors: List[str]) -> dict:
    """Return marker configuration for node traces."""
    return {
        "size": 15,
        "color": colors,
        "opacity": 0.9,
        "line": {"color": "rgba(0,0,0,0.8)", "width": 2},
        "symbol": "circle",
    }


def _build_node_text_font() -> dict:
    """Return text font configuration for node labels."""
    return {"size": 12, "color": "black"}


def _validate_relationship_graph(graph: AssetRelationshipGraph) -> None:
    """Validate graph object required for relationship trace generation."""
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("graph must be an AssetRelationshipGraph instance")
    if not hasattr(graph, "relationships") or not isinstance(graph.relationships, dict):
        raise ValueError("graph must have a relationships dictionary")


def _normalize_and_validate_relationship_positions(
    positions: Sequence[Sequence[float]],
    asset_ids: List[str],
) -> Sequence[Sequence[float]]:
    """Normalize positions and validate length against asset IDs."""
    positions_arr = _normalize_positions(positions)
    if len(positions_arr) != len(asset_ids):
        raise ValueError("positions array length must match asset_ids length")
    return positions_arr


def _create_trace_for_group(
    relationship_key: tuple[str, bool],
    relationships: List[dict],
    positions: Sequence[Sequence[float]],
    asset_id_index: Dict[str, int],
) -> go.Scatter3d:
    """Build a Plotly Scatter3d trace for a group of relationships of the same type and direction.

    Generates 3D edge coordinates, constructs hover texts, and applies line styling and naming conventions.
    """
    rel_type, is_bidirectional = relationship_key
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
    positions: Sequence[Sequence[float]],
    asset_ids: List[str],
    colors: List[str],
    hover_texts: List[str],
) -> go.Scatter3d:
    """Create node trace for 3D visualization. Validates all inputs before rendering."""
    positions_arr = _normalize_positions(positions)
    _validate_node_trace_inputs(positions_arr, asset_ids, colors, hover_texts)
    x_values, y_values, z_values = _extract_node_coordinates(positions_arr)
    return go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode="markers+text",
        marker=_build_node_marker(colors),
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont=_build_node_text_font(),
        name="Assets",
        visible=True,
    )


def _create_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Sequence[Sequence[float]],
    asset_ids: List[str],
    relationship_filters: Optional[Dict[str, bool]] = None,
) -> List[go.Scatter3d]:
    """Create one trace per (rel_type, directionality) group for batch addition."""
    _validate_relationship_graph(graph)
    positions_arr = _normalize_and_validate_relationship_positions(positions, asset_ids)

    asset_id_index = _build_asset_id_index(asset_ids)
    relationship_groups = _collect_and_group_relationships(graph, asset_ids, relationship_filters)

    return [
        _create_trace_for_group((rel_type, is_bidirectional), rels, positions_arr, asset_id_index)
        for (rel_type, is_bidirectional), rels in relationship_groups.items()
        if rels
    ]
