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
) -> Dict[str, Tuple[float, float]]:
    if layout_type == "circular":
        return _create_circular_layout(asset_ids)
    if layout_type == "grid":
        return _create_grid_layout(asset_ids)
    # Default: spring — project 3D positions to 2D
    if hasattr(graph, "get_3d_visualization_data_enhanced"):
        positions_3d_array, asset_ids_ordered, _, _ = (
            graph.get_3d_visualization_data_enhanced()
        )
        positions_3d = {
            asset_ids_ordered[i]: tuple(positions_3d_array[i])
            for i in range(len(asset_ids_ordered))
        }
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
    """Create 2D visualization of asset relationship graph."""
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

    positions = _resolve_positions(graph, layout_type, asset_ids)

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

    fig.add_trace(_create_node_trace(graph, positions, asset_ids))

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
