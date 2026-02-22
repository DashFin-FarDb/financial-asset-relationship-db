import logging
from typing import Dict, Optional

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph

# Sub-module re-exports — kept here so existing imports from this module continue to work.
from src.visualizations.graph_visuals_constants import REL_TYPE_COLORS  # noqa: F401
from src.visualizations.graph_visuals_data import _build_asset_id_index  # noqa: F401
from src.visualizations.graph_visuals_data import _build_edge_coordinates_optimized  # noqa: F401
from src.visualizations.graph_visuals_data import _build_hover_texts  # noqa: F401
from src.visualizations.graph_visuals_data import _build_relationship_index  # noqa: F401
from src.visualizations.graph_visuals_data import _collect_and_group_relationships  # noqa: F401
from src.visualizations.graph_visuals_layout import _calculate_visible_relationships  # noqa: F401
from src.visualizations.graph_visuals_layout import _generate_dynamic_title  # noqa: F401
from src.visualizations.graph_visuals_layout import (
    _configure_3d_layout,
    _prepare_layout_config,
)
from src.visualizations.graph_visuals_traces import _create_trace_for_group  # noqa: F401
from src.visualizations.graph_visuals_traces import _format_trace_name  # noqa: F401
from src.visualizations.graph_visuals_traces import (
    _create_directional_arrows,
    _create_node_trace,
    _create_relationship_traces,
)
from src.visualizations.graph_visuals_validation import (
    _validate_filter_parameters,
    _validate_relationship_filters,
    _validate_visualization_data,
)

logger = logging.getLogger(__name__)


def visualize_3d_graph(graph: AssetRelationshipGraph) -> go.Figure:
    """
    Create a 3D visualization of an asset relationship graph.
    
    Parameters:
        graph (AssetRelationshipGraph): The graph to visualize; must implement
            `get_3d_visualization_data_enhanced()` to provide node positions,
            asset identifiers, colors, and hover texts.
    
    Returns:
        go.Figure: A Plotly 3D figure containing node markers and relationship traces.
    
    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph instance or does
            not provide the required `get_3d_visualization_data_enhanced` method.
    """
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(graph, "get_3d_visualization_data_enhanced"):
        raise ValueError("Invalid graph data provided")

    positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    fig = go.Figure()

    relationship_traces = _create_relationship_traces(graph, positions, asset_ids)
    if relationship_traces:
        fig.add_traces(relationship_traces)

    arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
    if arrow_traces:
        fig.add_traces(arrow_traces)

    fig.add_trace(_create_node_trace(positions, asset_ids, colors, hover_texts))

    dynamic_title, options = _prepare_layout_config(len(asset_ids), relationship_traces)
    _configure_3d_layout(fig, dynamic_title, options)

    return fig


def visualize_3d_graph_with_filters(
    graph: AssetRelationshipGraph,
    show_same_sector: bool = True,
    show_market_cap: bool = True,
    show_correlation: bool = True,
    show_corporate_bond: bool = True,
    show_commodity_currency: bool = True,
    show_income_comparison: bool = True,
    show_regulatory: bool = True,
    show_all_relationships: bool = True,
    toggle_arrows: bool = True,
) -> go.Figure:
    """
    Create a 3D visualization of an AssetRelationshipGraph with selective relationship-type filters.
    
    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph to visualize.
        show_same_sector (bool): Include same-sector relationships.
        show_market_cap (bool): Include market-cap-similar relationships.
        show_correlation (bool): Include correlation relationships.
        show_corporate_bond (bool): Include corporate-bond-to-equity relationships.
        show_commodity_currency (bool): Include commodity-currency relationships.
        show_income_comparison (bool): Include income-comparison relationships.
        show_regulatory (bool): Include regulatory-impact relationships.
        show_all_relationships (bool): If True, ignore per-type filters and show all relationships.
        toggle_arrows (bool): Show directional arrows for unidirectional relationships.
    
    Returns:
        fig (plotly.graph_objs.Figure): Configured 3D Plotly figure representing the graph.
    
    Raises:
        ValueError: If `graph` is not an AssetRelationshipGraph instance or lacks required visualization data.
    """
    if not isinstance(graph, AssetRelationshipGraph) or not hasattr(graph, "get_3d_visualization_data_enhanced"):
        raise ValueError("graph must be an AssetRelationshipGraph instance " "with get_3d_visualization_data_enhanced")

    filter_params = {
        "show_same_sector": show_same_sector,
        "show_market_cap": show_market_cap,
        "show_correlation": show_correlation,
        "show_corporate_bond": show_corporate_bond,
        "show_commodity_currency": show_commodity_currency,
        "show_income_comparison": show_income_comparison,
        "show_regulatory": show_regulatory,
        "show_all_relationships": show_all_relationships,
        "toggle_arrows": toggle_arrows,
    }
    _validate_filter_parameters(filter_params)

    if show_all_relationships:
        relationship_filters: Optional[Dict[str, bool]] = None
    else:
        relationship_filters = {
            "same_sector": show_same_sector,
            "market_cap_similar": show_market_cap,
            "correlation": show_correlation,
            "corporate_bond_to_equity": show_corporate_bond,
            "commodity_currency": show_commodity_currency,
            "income_comparison": show_income_comparison,
            "regulatory_impact": show_regulatory,
        }
        _validate_relationship_filters(relationship_filters)
        if not any(relationship_filters.values()):
            logger.warning("All relationship filters are disabled. " "Visualization will show no relationships.")

    positions, asset_ids, colors, hover_texts = graph.get_3d_visualization_data_enhanced()
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    fig = go.Figure()

    relationship_traces = _create_relationship_traces(graph, positions, asset_ids, relationship_filters)
    if relationship_traces:
        fig.add_traces(relationship_traces)

    if toggle_arrows:
        arrow_traces = _create_directional_arrows(graph, positions, asset_ids)
        if arrow_traces:
            fig.add_traces(arrow_traces)

    fig.add_trace(_create_node_trace(positions, asset_ids, colors, hover_texts))

    dynamic_title, options = _prepare_layout_config(len(asset_ids), relationship_traces)
    _configure_3d_layout(fig, dynamic_title, options)

    return fig