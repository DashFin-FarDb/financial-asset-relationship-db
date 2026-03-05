"""
2D graph visualization module for financial asset relationships.

This module provides 2D visualization capabilities for asset relationship
graphs,
including multiple layout algorithms (spring, circular, grid) and
relationship filtering.


"""

import logging
import math
from typing import Dict, List, Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals_traces import _create_node_trace

logger = logging.getLogger(__name__)

# Color mapping for relationship types (shared with 3D visuals)
REL_TYPE_COLORS = {
    "same_sector": "#FF6B6B",
    "market_cap_similar": "#4ECDC4",
    "correlation": "#45B7D1",
    "corporate_bond_to_equity": "#96CEB4",
    "commodity_currency": "#FFEAA7",
    "income_comparison": "#DDA0DD",
    "regulatory_impact": "#FFA07A",
}


def _create_circular_layout(asset_ids: List[str]) -> Dict[str, Tuple[float, float]]:
    """Create circular layout for 2D visualization.

    Args:
        asset_ids: List of asset IDs to position

    Returns:
        Dictionary mapping asset IDs to (x, y) positions on a unit circle
    """
    if not asset_ids:
        return {}

    n = len(asset_ids)
    positions = {}

    for i, asset_id in enumerate(asset_ids):
        angle = 2 * math.pi * i / n
        x = math.cos(angle)
        y = math.sin(angle)
        positions[asset_id] = (x, y)

    return positions


def _create_grid_layout(asset_ids: List[str]) -> Dict[str, Tuple[float, float]]:
    """Create grid layout for 2D visualization.

    Args:
        asset_ids: List of asset IDs to position

    Returns:
        Dictionary mapping asset IDs to (x, y) positions in a grid
    """
    if not asset_ids:
        return {}

    n = len(asset_ids)
    cols = int(math.ceil(math.sqrt(n)))

    positions = {}
    for i, asset_id in enumerate(asset_ids):
        row = i // cols
        col = i % cols
        positions[asset_id] = (float(col), float(row))

    return positions


def _create_spring_layout_2d(
    positions_3d: Dict[str, Tuple[float, float, float]], asset_ids: List[str]
) -> Dict[str, Tuple[float, float]]:
    """Convert 3D spring layout positions to 2D by dropping z-coordinate.

    Args:
        positions_3d: Dictionary mapping asset IDs to (x, y, z) positions
        asset_ids: List of asset IDs

    Returns:
        Dictionary mapping asset IDs to (x, y) positions
    """
    if not positions_3d or not asset_ids:
        return {}

    positions_2d = {}
    for asset_id in asset_ids:
        if asset_id in positions_3d:
            pos_3d = positions_3d[asset_id]
            # Handle both tuple and array-like positions
            if hasattr(pos_3d, "__getitem__"):
                positions_2d[asset_id] = (float(pos_3d[0]), float(pos_3d[1]))

    return positions_2d


def _build_relationship_filters(
    relationship_options: Dict[str, bool],
) -> Dict[str, bool]:
    """Build relationship-type visibility filters from UI toggles."""
    return {
        "same_sector": relationship_options["show_same_sector"],
        "market_cap_similar": relationship_options["show_market_cap"],
        "correlation": relationship_options["show_correlation"],
        "corporate_bond_to_equity": relationship_options["show_corporate_bond"],
        "commodity_currency": relationship_options["show_commodity_currency"],
        "income_comparison": relationship_options["show_income_comparison"],
        "regulatory_impact": relationship_options["show_regulatory"],
    }


def _group_relationships_by_type(
    graph: AssetRelationshipGraph,
    asset_ids: List[str],
    positions: Dict[str, Tuple[float, float]],
    relationship_filters: Dict[str, bool] | None,
) -> Dict[str, List[Dict[str, object]]]:
    """Collect eligible relationships grouped by relationship type."""
    asset_id_set = set(asset_ids)
    relationship_groups: Dict[str, List[Dict[str, object]]] = {}

    for source_id in asset_ids:
        if source_id not in positions:
            continue
        source_relationships = graph.relationships.get(source_id, [])
        for target_id, rel_type, strength in source_relationships:
            if target_id not in positions or target_id not in asset_id_set:
                continue
            if relationship_filters is not None and not relationship_filters.get(rel_type, True):
                continue
            relationship_groups.setdefault(rel_type, []).append(
                {"source_id": source_id, "target_id": target_id, "strength": strength}
            )

    return relationship_groups


def _build_relationship_trace(
    rel_type: str,
    relationships: List[Dict[str, object]],
    positions: Dict[str, Tuple[float, float]],
) -> go.Scatter:
    """Build one line trace for a relationship type."""
    edges_x: List[float | None] = []
    edges_y: List[float | None] = []
    hover_texts: List[str | None] = []

    for rel in relationships:
        source_id = str(rel["source_id"])
        target_id = str(rel["target_id"])
        if source_id not in positions or target_id not in positions:
            continue
        strength = float(rel["strength"])
        source_pos = positions[source_id]
        target_pos = positions[target_id]
        edges_x.extend([source_pos[0], target_pos[0], None])
        edges_y.extend([source_pos[1], target_pos[1], None])
        hover_text = f"{source_id} → {target_id}<br>Type: {rel_type}<br>Strength: {strength:.2f}"
        hover_texts.extend([hover_text, hover_text, None])

    return go.Scatter(
        x=edges_x,
        y=edges_y,
        mode="lines",
        line={"color": REL_TYPE_COLORS.get(rel_type, "#888888"), "width": 2},
        hovertext=hover_texts,
        hoverinfo="text",
        name=rel_type.replace("_", " ").title(),
        showlegend=True,
    )


def _create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    relationship_filters: Dict[str, bool] | None = None,
) -> List[go.Scatter]:
    """
    Build Plotly Scatter traces for asset-to-asset relationships, grouped and
    colored by relationship type and filtered by the provided toggles.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing relationship tuples
            of the form (target_id, rel_type, strength).
        positions (Dict[str, Tuple[float, float]]): Mapping from asset ID to 2D
            (x, y) coordinates used to draw edges.
        asset_ids (List[str]): Sequence of asset IDs to consider when collecting
            relationships.
        relationship_filters (Dict[str, bool] | None): Optional mapping of
            relationship type to enabled status. If None, all relationship
            types are included.

    Returns:
        List[go.Scatter]: A list of Plotly Scatter traces where each trace
            represents one relationship type (edges drawn as lines with hover
            text showing source → target, type, and strength). Returns an
            empty list if `asset_ids` or `positions` is empty.
    """
    if not asset_ids or not positions:
        return []

    valid_asset_ids = [asset_id for asset_id in asset_ids if asset_id in positions]
    if not valid_asset_ids:
        return []

    relationship_groups = _group_relationships_by_type(
        graph,
        valid_asset_ids,
        positions,
        relationship_filters,
    )

    return [
        _build_relationship_trace(rel_type, relationships, positions)
        for rel_type, relationships in relationship_groups.items()
        if relationships
    ]


def visualize_2d_graph(
    graph: AssetRelationshipGraph,
    layout_type: str = "spring",
    *relationship_flags: bool,
    **relationship_options: bool,
) -> go.Figure:
    """
    Render a 2D Plotly visualization of an asset relationship graph using a
    chosen layout and relationship filters.

    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph to visualize.
        layout_type (str): Layout algorithm to use; one of "spring", "circular",
            or "grid".
        *relationship_flags (bool): Optional positional relationship toggles
            in this order: show_same_sector, show_market_cap,
            show_correlation, show_corporate_bond,
            show_commodity_currency, show_income_comparison,
            show_regulatory, show_all_relationships.
        **relationship_options (bool): Optional relationship visibility
            toggles. Supported keys are `show_same_sector`, `show_market_cap`,
            `show_correlation`, `show_corporate_bond`,
            `show_commodity_currency`, `show_income_comparison`,
            `show_regulatory`, and `show_all_relationships`.

    Returns:
        go.Figure: A Plotly Figure containing the 2D network visualization of
            assets and filtered relationships.

    Raises:
        ValueError: If `graph` is not an instance of AssetRelationshipGraph.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("Invalid graph data provided")

    option_keys = [
        "show_same_sector",
        "show_market_cap",
        "show_correlation",
        "show_corporate_bond",
        "show_commodity_currency",
        "show_income_comparison",
        "show_regulatory",
        "show_all_relationships",
    ]
    if len(relationship_flags) > len(option_keys):
        raise ValueError("Too many positional relationship flags provided")

    positional_options = {key: bool(value) for key, value in zip(option_keys, relationship_flags, strict=False)}
    option_defaults: Dict[str, bool] = {
        "show_same_sector": True,
        "show_market_cap": True,
        "show_correlation": True,
        "show_corporate_bond": True,
        "show_commodity_currency": True,
        "show_income_comparison": True,
        "show_regulatory": True,
        "show_all_relationships": False,
    }
    resolved_options = option_defaults | positional_options | relationship_options

    # Get asset data
    asset_ids = list(graph.assets.keys())

    if not asset_ids:
        # Return empty figure for empty graph
        fig = go.Figure()
        fig.update_layout(
            title="2D Asset Relationship Network (No Assets)",
            plot_bgcolor="white",
            paper_bgcolor="#F8F9FA",
        )
        return fig

    # Create layout based on type
    if layout_type == "circular":
        positions = _create_circular_layout(asset_ids)
    elif layout_type == "grid":
        positions = _create_grid_layout(asset_ids)
    else:  # Default to spring layout
        # Get 3D positions and convert to 2D
        if hasattr(graph, "get_3d_visualization_data_enhanced"):
            (
                positions_3d_array,
                asset_ids_ordered,
                _,
                _,
            ) = graph.get_3d_visualization_data_enhanced()
            # Convert array to dictionary
            positions_3d = {asset_ids_ordered[i]: tuple(positions_3d_array[i]) for i in range(len(asset_ids_ordered))}
            positions = _create_spring_layout_2d(positions_3d, asset_ids)
        else:
            # Fallback to circular if 3D data not available
            positions = _create_circular_layout(asset_ids)

    # Create figure
    fig = go.Figure()
    valid_asset_ids = [asset_id for asset_id in asset_ids if asset_id in positions]

    # Add relationship traces
    relationship_filters: Dict[str, bool] | None = (
        None if resolved_options["show_all_relationships"] else _build_relationship_filters(resolved_options)
    )
    relationship_traces = _create_2d_relationship_traces(
        graph,
        positions,
        valid_asset_ids,
        relationship_filters=relationship_filters,
    )

    for trace in relationship_traces:
        fig.add_trace(trace)

    fig.add_trace(_create_node_trace(graph, positions, valid_asset_ids))

    # Update layout
    layout_name = layout_type.capitalize()
    fig.update_layout(
        title=f"2D Asset Relationship Network ({layout_name} Layout)",
        plot_bgcolor="white",
        paper_bgcolor="#F8F9FA",
        xaxis={
            "showgrid": True,
            "gridcolor": "rgba(200, 200, 200, 0.3)",
            "zeroline": False,
            "showticklabels": False,
        },
        yaxis={
            "showgrid": True,
            "gridcolor": "rgba(200, 200, 200, 0.3)",
            "zeroline": False,
            "showticklabels": False,
        },
        width=1200,
        height=800,
        hovermode="closest",
        showlegend=True,
        legend={
            "x": 0.02,
            "y": 0.98,
            "bgcolor": "rgba(255, 255, 255, 0.8)",
            "bordercolor": "rgba(0, 0, 0, 0.3)",
            "borderwidth": 1,
        },
        annotations=[
            {
                "text": f"Layout: {layout_name}",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": -0.05,
                "showarrow": False,
                "font": {"size": 12, "color": "gray"},
            }
        ],
    )

    return fig
