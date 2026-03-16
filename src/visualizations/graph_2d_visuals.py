"""
2D graph visualization module for financial asset relationships.

This module provides 2D visualization capabilities for asset relationship
graphs,
including multiple layout algorithms (spring, circular, grid) and
relationship filtering.


"""

import logging
import math
from typing import Dict, List, Tuple, cast

import plotly.graph_objects as go  # type: ignore[import-untyped]

from src.logic.asset_graph import AssetRelationshipGraph

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


def _create_circular_layout(
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
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


def _create_grid_layout(
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
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


def _create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    show_same_sector: bool = True,
    show_market_cap: bool = True,
    show_correlation: bool = True,
    show_corporate_bond: bool = True,
    show_commodity_currency: bool = True,
    show_income_comparison: bool = True,
    show_regulatory: bool = True,
    show_all_relationships: bool = False,
) -> List[go.Scatter]:
    """
    Build Plotly Scatter traces for asset-to-asset relationships, grouped and
    colored by relationship type and filtered by the provided toggles.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing relationship tuples
            of the form (target_id, rel_type, strength).
        positions (Dict[str, Tuple[float, float]]): Mapping from asset ID to 2D
            (x, y) coordinates used to draw edges.
        asset_ids (List[str]):
            Sequence of asset IDs to consider when collecting relationships.
        show_same_sector (bool): Include relationships of type "same_sector".
        show_market_cap (bool): Include relationships of type
            "market_cap_similar".
        show_correlation (bool): Include relationships of type "correlation".
        show_corporate_bond (bool): Include relationships of type
            "corporate_bond_to_equity".
        show_commodity_currency (bool): Include relationships of type
            "commodity_currency".
        show_income_comparison (bool): Include relationships of type
            "income_comparison".
        show_regulatory (bool):
            Include relationships of type "regulatory_impact".
        show_all_relationships (bool): If True, ignore individual show_* flags
            and include all relationship types found in the graph.

    Returns:
        List[go.Scatter]: A list of Plotly Scatter traces where each trace
            represents one relationship type (edges drawn as lines with hover
            text showing source → target, type, and strength). Returns an
            empty list if `asset_ids` or `positions` is empty.
    """
    if not asset_ids or not positions:
        return []

    relationship_filters = _relationship_visibility_filters(
        show_same_sector=show_same_sector,
        show_market_cap=show_market_cap,
        show_correlation=show_correlation,
        show_corporate_bond=show_corporate_bond,
        show_commodity_currency=show_commodity_currency,
        show_income_comparison=show_income_comparison,
        show_regulatory=show_regulatory,
    )
    relationship_groups = _group_relationships_by_type(
        graph=graph,
        positions=positions,
        asset_ids=asset_ids,
        relationship_filters=relationship_filters,
        show_all_relationships=show_all_relationships,
    )
    return [
        _build_relationship_trace(
            rel_type=rel_type,
            relationships=relationships,
            positions=positions,
        )
        for rel_type, relationships in relationship_groups.items()
        if relationships
    ]


def _relationship_visibility_filters(
    *,
    show_same_sector: bool,
    show_market_cap: bool,
    show_correlation: bool,
    show_corporate_bond: bool,
    show_commodity_currency: bool,
    show_income_comparison: bool,
    show_regulatory: bool,
) -> Dict[str, bool]:
    """Return relationship-type filter flags keyed by internal type name."""
    return {
        "same_sector": show_same_sector,
        "market_cap_similar": show_market_cap,
        "correlation": show_correlation,
        "corporate_bond_to_equity": show_corporate_bond,
        "commodity_currency": show_commodity_currency,
        "income_comparison": show_income_comparison,
        "regulatory_impact": show_regulatory,
    }


def _is_relationship_filtered(
    rel_type: str,
    relationship_filters: Dict[str, bool],
    show_all_relationships: bool,
) -> bool:
    """Return True when a relationship type should be hidden."""
    return (
        not show_all_relationships
        and rel_type in relationship_filters
        and not relationship_filters[rel_type]
    )


def _group_relationships_by_type(
    *,
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    relationship_filters: Dict[str, bool],
    show_all_relationships: bool,
) -> Dict[str, list[Dict[str, object]]]:
    """Group source-target relationships by relationship type."""
    asset_id_set = set(asset_ids)
    relationship_groups: Dict[str, list[Dict[str, object]]] = {}

    for source_id in asset_ids:
        for target_id, rel_type, strength in graph.relationships.get(
            source_id, []
        ):
            if target_id not in positions or target_id not in asset_id_set:
                continue
            if _is_relationship_filtered(
                rel_type=rel_type,
                relationship_filters=relationship_filters,
                show_all_relationships=show_all_relationships,
            ):
                continue

            relationship_groups.setdefault(rel_type, []).append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "strength": strength,
                }
            )
    return relationship_groups


def _build_relationship_trace(
    *,
    rel_type: str,
    relationships: list[Dict[str, object]],
    positions: Dict[str, Tuple[float, float]],
) -> go.Scatter:
    """Create one Plotly edge trace for a single relationship type."""
    edges_x: list[float | None] = []
    edges_y: list[float | None] = []
    hover_texts: list[str | None] = []

    for rel in relationships:
        source_id = str(rel["source_id"])
        target_id = str(rel["target_id"])
        strength = cast(float, rel["strength"])
        source_pos = positions[source_id]
        target_pos = positions[target_id]
        edges_x.extend([source_pos[0], target_pos[0], None])
        edges_y.extend([source_pos[1], target_pos[1], None])
        hover_text = (
            f"{source_id} → {target_id}<br>"
            f"Type: {rel_type}<br>"
            f"Strength: {strength:.2f}"
        )
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


def _resolve_layout_positions(
    graph: AssetRelationshipGraph,
    layout_type: str,
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
    """Resolve 2D positions for the requested layout type."""
    if layout_type == "circular":
        return _create_circular_layout(asset_ids)
    if layout_type == "grid":
        return _create_grid_layout(asset_ids)
    return _spring_or_fallback_positions(graph, asset_ids)


def _spring_or_fallback_positions(
    graph: AssetRelationshipGraph,
    asset_ids: List[str],
) -> Dict[str, Tuple[float, float]]:
    """Build spring-layout positions when available, else use circular."""
    if not hasattr(graph, "get_3d_visualization_data_enhanced"):
        return _create_circular_layout(asset_ids)
    (
        positions_3d_array,
        asset_ids_ordered,
        _,
        _,
    ) = graph.get_3d_visualization_data_enhanced()
    positions_3d = {
        asset_ids_ordered[i]: tuple(positions_3d_array[i])
        for i in range(len(asset_ids_ordered))
    }
    circular_fallback = _create_circular_layout(asset_ids)
    for asset_id in asset_ids:
        if asset_id not in positions_3d:
            fb = circular_fallback.get(asset_id, (0.0, 0.0))
            positions_3d[asset_id] = (fb[0], fb[1], 0.0)
    return _create_spring_layout_2d(positions_3d, asset_ids)


def _asset_class_label(asset: object) -> str:
    """Return asset class label regardless of enum/string representation."""
    asset_class = getattr(asset, "asset_class", "")
    if hasattr(asset_class, "value"):
        return str(asset_class.value)
    return str(asset_class)


def _build_node_visual_components(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
) -> Tuple[list[float], list[float], list[str], list[int], list[str]]:
    """Build x/y coordinates, colors, sizes, and hover texts for nodes."""
    node_x = [positions[asset_id][0] for asset_id in asset_ids]
    node_y = [positions[asset_id][1] for asset_id in asset_ids]
    color_map = {
        "equity": "#1f77b4",
        "fixed_income": "#2ca02c",
        "commodity": "#ff7f0e",
        "currency": "#d62728",
        "derivative": "#9467bd",
    }
    colors: list[str] = []
    node_sizes: list[int] = []
    hover_texts: list[str] = []
    for asset_id in asset_ids:
        asset = graph.assets[asset_id]
        asset_class = _asset_class_label(asset)
        colors.append(color_map.get(asset_class.lower(), "#7f7f7f"))
        num_connections = len(graph.relationships.get(asset_id, []))
        node_sizes.append(20 + min(num_connections * 5, 30))
        hover_texts.append(f"{asset_id}<br>Class: {asset_class}")
    return node_x, node_y, colors, node_sizes, hover_texts


def visualize_2d_graph(
    graph: AssetRelationshipGraph,
    layout_type: str = "spring",
    show_same_sector: bool = True,
    show_market_cap: bool = True,
    show_correlation: bool = True,
    show_corporate_bond: bool = True,
    show_commodity_currency: bool = True,
    show_income_comparison: bool = True,
    show_regulatory: bool = True,
    show_all_relationships: bool = False,
) -> go.Figure:
    """
    Render a 2D Plotly visualization of an asset relationship graph using a
    chosen layout and relationship filters.

    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph to visualize.
        layout_type (str):
            Layout algorithm to use; one of "spring", "circular", or "grid".
        show_same_sector (bool): Include "same sector"
            relationships when True.
        show_market_cap (bool): Include "market cap" relationships when True.
        show_correlation (bool): Include "correlation"
            relationships when True.
        show_corporate_bond (bool): Include "corporate bond"
            relationships when True.
        show_commodity_currency (bool): Include "commodity/currency"
            relationships when True.
        show_income_comparison (bool): Include "income comparison"
            relationships when True.
        show_regulatory (bool): Include "regulatory" relationships when True.
        show_all_relationships (bool): If True, override individual toggles
            and include all relationship types.

    Returns:
        go.Figure: A Plotly Figure containing the 2D network visualization of
            assets and filtered relationships.

    Raises:
        ValueError: If `graph` is not an instance of AssetRelationshipGraph.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("Invalid graph data provided")

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

    positions = _resolve_layout_positions(graph, layout_type, asset_ids)

    # Create figure
    fig = go.Figure()

    # Add relationship traces
    relationship_traces = _create_2d_relationship_traces(
        graph,
        positions,
        asset_ids,
        show_same_sector=show_same_sector,
        show_market_cap=show_market_cap,
        show_correlation=show_correlation,
        show_corporate_bond=show_corporate_bond,
        show_commodity_currency=show_commodity_currency,
        show_income_comparison=show_income_comparison,
        show_regulatory=show_regulatory,
        show_all_relationships=show_all_relationships,
    )

    for trace in relationship_traces:
        fig.add_trace(trace)

    (
        node_x,
        node_y,
        colors,
        node_sizes,
        hover_texts,
    ) = _build_node_visual_components(
        graph=graph,
        positions=positions,
        asset_ids=asset_ids,
    )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker={
            "size": node_sizes,
            "color": colors,
            "opacity": 0.9,
            "line": {"color": "rgba(0,0,0,0.8)", "width": 2},
        },
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont={"size": 10, "color": "black"},
        name="Assets",
        showlegend=False,
    )

    fig.add_trace(node_trace)

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
