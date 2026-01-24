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


def _create_circular_layout(asset_ids: List[str]) -> dict[str, Tuple[float, float]]:
    """
    Compute 2D positions for asset IDs evenly spaced on the unit circle.

    Parameters:
        asset_ids (List[str]): Ordered list of asset IDs to place around the circle.

    Returns:
        dict[str, Tuple[float, float]]: Mapping from each asset ID to its (x, y)
            coordinates on the unit circle.
            Returns an empty dict if `asset_ids` is empty.
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


def _create_grid_layout(asset_ids: List[str]) -> dict[str, Tuple[float, float]]:
    """
    Arrange asset IDs on a rectangular grid and return their 2D coordinates.

    Positions are assigned left-to-right, top-to-bottom.

    Columns increase along x and rows along y, starting at (0.0, 0.0).

    If `asset_ids` is empty, an empty dictionary is returned.

    Parameters:
        asset_ids (List[str]): Ordered list of asset IDs to place on the grid.

    Returns:
        dict[str, Tuple[float, float]]: Mapping from each asset ID to its (x, y) grid
            coordinates as floats.
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
    positions_3d: dict[str, Tuple[float, float, float]], asset_ids: List[str]
) -> dict[str, Tuple[float, float]]:
    """
    Convert 3D layout coordinates to 2D coordinates by dropping the z component.

    Parameters:
        positions_3d (dict[str, Tuple[float, float, float]]):
            Mapping of asset ID to 3D position.
        asset_ids (List[str]):
            Asset IDs to include in the output.

    Returns:
        dict[str, Tuple[float, float]]: Mapping of each asset ID
            from asset_ids present in positions_3d to a 2-tuple (x, y), with
            coordinates cast to float. Returns an empty dict if inputs are
            empty or no provided asset_ids exist in positions_3d.
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
    positions: dict[str, Tuple[float, float]],
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
    Create Plotly line traces representing relationships between assets,
    applying per-type filters.

    Parameters:
        graph: AssetRelationshipGraph containing relationships indexed by
            source asset ID.
        positions: Mapping of asset IDs to 2D (x, y) coordinates used to draw edges.
        asset_ids: Ordered list of asset IDs to consider when building relationships.
        show_same_sector: Include "same_sector" relationships.
        show_market_cap: Include "market_cap_similar" relationships.
        show_correlation: Include "correlation" relationships.
        show_corporate_bond: Include "corporate_bond_to_equity" relationships.
        show_commodity_currency: Include "commodity_currency" relationships.
        show_income_comparison: Include "income_comparison" relationships.
        show_regulatory: Include "regulatory_impact" relationships.
        show_all_relationships: If true, ignore individual show_* flags and include all
            relationship types.

    Returns:
        List of Plotly Scatter traces, one per relationship type
            that passed filtering.
        Empty list if no relationships.
    """
    if not asset_ids or not positions:
        return []

    traces = []
    asset_id_set = set(asset_ids)

    # Construct relationship filters dictionary
    relationship_filters = {
        "same_sector": show_same_sector,
        "market_cap_similar": show_market_cap,
        "correlation": show_correlation,
        "corporate_bond_to_equity": show_corporate_bond,
        "commodity_currency": show_commodity_currency,
        "income_comparison": show_income_comparison,
        "regulatory_impact": show_regulatory,
    }

    # Group relationships by type
    relationship_groups = {}

    for source_id in asset_ids:
        if source_id not in graph.relationships:
            continue

        for target_id, rel_type, strength in graph.relationships[source_id]:
            # Skip if target not in positions
            if target_id not in positions or target_id not in asset_id_set:
                continue

            # Apply filters if not showing all relationships
            if (
                not show_all_relationships
                and rel_type in relationship_filters
                and not relationship_filters[rel_type]
            ):
                continue

            # Group by relationship type
            if rel_type not in relationship_groups:
                relationship_groups[rel_type] = []

            relationship_groups[rel_type].append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "strength": strength,
                }
            )

    # Create traces for each relationship type
    for rel_type, relationships in relationship_groups.items():
        if not relationships:
            continue

        edges_x = []
        edges_y = []
        hover_texts = []

        for rel in relationships:
            source_pos = positions[rel["source_id"]]
            target_pos = positions[rel["target_id"]]

            edges_x.extend([source_pos[0], target_pos[0], None])
            edges_y.extend([source_pos[1], target_pos[1], None])

            hover_text = (
                f"{rel['source_id']} → {rel['target_id']}<br>"
                f"Type: {rel_type}<br>"
                f"Strength: {rel['strength']:.2f}"
            )
            hover_texts.extend([hover_text, hover_text, None])

        color = REL_TYPE_COLORS.get(rel_type, "#888888")
        trace_name = rel_type.replace("_", " ").title()

        trace = go.Scatter(
            x=edges_x,
            y=edges_y,
            mode="lines",
            line=dict(color=color, width=2),
            hovertext=hover_texts,
            hoverinfo="text",
            name=trace_name,
            showlegend=True,
        )
        traces.append(trace)

    return traces


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
    """Create 2D visualization of asset relationship graph.

    Args:
        graph: Asset relationship graph to visualize
        layout_type: Layout algorithm to use ('spring', 'circular', 'grid')
        show_same_sector: Show same sector relationships
        show_market_cap: Show market cap relationships
        show_correlation: Show correlation relationships
        show_corporate_bond: Show corporate bond relationships
        show_commodity_currency: Show commodity currency relationships
        show_income_comparison: Show income comparison relationships
        show_regulatory: Show regulatory relationships
        show_all_relationships: Master toggle to show all relationships

    Returns:
        Plotly Figure object with 2D visualization
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
            positions_3d = {
                asset_ids_ordered[i]: tuple(positions_3d_array[i])
                for i in range(len(asset_ids_ordered))
            }
            positions = _create_spring_layout_2d(positions_3d, asset_ids)
        else:
            # Fallback to circular if 3D data not available
            positions = _create_circular_layout(asset_ids)

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

    # Add node trace
    node_x = [positions[asset_id][0] for asset_id in asset_ids]
    node_y = [positions[asset_id][1] for asset_id in asset_ids]

    # Get colors for nodes
    colors = []
    for asset_id in asset_ids:
        asset = graph.assets[asset_id]
        asset_class = (
            asset.asset_class.value
            if hasattr(asset.asset_class, "value")
            else str(asset.asset_class)
        )

        # Color mapping by asset class
        color_map = {
            "equity": "#1f77b4",
            "fixed_income": "#2ca02c",
            "commodity": "#ff7f0e",
            "currency": "#d62728",
            "derivative": "#9467bd",
        }
        colors.append(color_map.get(asset_class.lower(), "#7f7f7f"))

    # Calculate node sizes based on connections
    node_sizes = []
    for asset_id in asset_ids:
        num_connections = len(graph.relationships.get(asset_id, []))
        size = 20 + min(num_connections * 5, 30)  # Size between 20 and 50
        node_sizes.append(size)

    # Create hover texts
    hover_texts = []
    for asset_id in asset_ids:
        asset = graph.assets[asset_id]
        hover_text = f"{asset_id}<br>Class: " + (
            asset.asset_class.value
            if hasattr(asset.asset_class, "value")
            else str(asset.asset_class)
        )
        hover_texts.append(hover_text)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(
            size=node_sizes,
            color=colors,
            opacity=0.9,
            line=dict(color="rgba(0,0,0,0.8)", width=2),
        ),
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont=dict(size=10, color="black"),
        name="Assets",
        showlegend=False,
    )

    fig.add_trace(node_trace)
    layout_name = layout_type.capitalize()
    fig.update_layout(
        title=f"2D Asset Relationship Network ({layout_name} Layout)",
        plot_bgcolor="white",
        paper_bgcolor="#F8F9FA",
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
            zeroline=False,
            showticklabels=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
            zeroline=False,
            showticklabels=False,
        ),
        width=1200,
        height=800,
        hovermode="closest",
        showlegend=True,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="rgba(0, 0, 0, 0.3)",
            borderwidth=1,
        ),
        annotations=[
            dict(
                text=f"Layout: {layout_name}",
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.05,
                showarrow=False,
                font=dict(size=12, color="gray"),
            )
        ],
    )

    return fig
