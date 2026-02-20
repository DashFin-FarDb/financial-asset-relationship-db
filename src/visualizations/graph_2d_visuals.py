from typing import Dict, List, Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals_constants import REL_TYPE_COLORS  # noqa: F401 — re-export
from src.visualizations.graph_2d_visuals_layouts import (
    _create_circular_layout,
    _create_grid_layout,
    _create_spring_layout_2d,
)
from src.visualizations.graph_2d_visuals_traces import (
    _create_2d_relationship_traces,
    _create_node_trace,
)

__all__ = ["visualize_2d_graph", "REL_TYPE_COLORS"]


def _resolve_positions(
    graph: AssetRelationshipGraph,
    layout_type: str,
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
    Build Plotly Scatter traces for asset-to-asset relationships, grouped and color-coded by relationship type and filtered by the provided toggles.
    
    Parameters:
        graph (AssetRelationshipGraph): Graph containing asset relationship entries (source -> [(target_id, rel_type, strength), ...]).
        layout_type (str): Layout hint ("spring", "circular", "grid") used by callers when converting or arranging traces.
        asset_ids (List[str]): Sequence of asset IDs to consider when collecting relationships and constructing traces.
        show_same_sector (bool): Include relationships of type "same_sector".
        show_market_cap (bool): Include relationships of type "market_cap_similar".
        show_correlation (bool): Include relationships of type "correlation".
        show_corporate_bond (bool): Include relationships of type "corporate_bond_to_equity".
        show_commodity_currency (bool): Include relationships of type "commodity_currency".
        show_income_comparison (bool): Include relationships of type "income_comparison".
        show_regulatory (bool): Include relationships of type "regulatory_impact".
        show_all_relationships (bool): If True, ignore individual show_* flags and include all relationship types present in the graph.
    
    Returns:
        List[go.Scatter]: A list of Plotly Scatter traces where each trace represents one relationship type (edges drawn as lines with hover text showing `source → target`, relationship type, and numeric strength). Returns an empty list if no relationships are available for the provided asset_ids.
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
            if not show_all_relationships and rel_type in relationship_filters and not relationship_filters[rel_type]:
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
        positions_3d = {asset_ids_ordered[i]: tuple(positions_3d_array[i]) for i in range(len(asset_ids_ordered))}
        return _create_spring_layout_2d(positions_3d, asset_ids)
    return _create_circular_layout(asset_ids)


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
    Render an interactive 2D Plotly network of assets and their relationships using the chosen layout and relationship filters.
    
    The layout_type controls node placement and accepts "spring", "circular", or "grid". Relationship toggle flags control which edge types are included; setting show_all_relationships to True overrides individual toggles and includes all relationship types.
    
    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph to visualize.
        layout_type (str): Layout algorithm to use; one of "spring", "circular", or "grid".
        show_same_sector (bool): Include "same sector" relationships when True.
        show_market_cap (bool): Include "market cap" relationships when True.
        show_correlation (bool): Include "correlation" relationships when True.
        show_corporate_bond (bool): Include "corporate bond" relationships when True.
        show_commodity_currency (bool): Include "commodity/currency" relationships when True.
        show_income_comparison (bool): Include "income comparison" relationships when True.
        show_regulatory (bool): Include "regulatory" relationships when True.
        show_all_relationships (bool): If True, ignore individual toggles and include all relationship types.
    
    Returns:
        go.Figure: A Plotly Figure containing asset nodes and filtered relationship edge traces.
    
    Raises:
        ValueError: If `graph` is not an instance of AssetRelationshipGraph.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise ValueError("Invalid graph data provided")

    asset_ids = list(graph.assets.keys())
    fig = go.Figure()

    if not asset_ids:
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

    for trace in _create_2d_relationship_traces(
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
    ):
        fig.add_trace(trace)

    # Add node trace
    node_x = [positions[asset_id][0] for asset_id in asset_ids]
    node_y = [positions[asset_id][1] for asset_id in asset_ids]

    # Get colors for nodes
    colors = []
    for asset_id in asset_ids:
        asset = graph.assets[asset_id]
        asset_class = asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class)

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
            asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class)
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