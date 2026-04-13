"""Compatibility facade for 3D graph visualization APIs.

This module preserves the legacy import surface while delegating
implementation to focused submodules.
"""

import logging
from typing import Dict, Mapping, Optional

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_visuals_constants import REL_TYPE_COLORS
from src.visualizations.graph_visuals_data import _build_asset_id_index, _build_relationship_index
from src.visualizations.graph_visuals_directional_arrows import _create_directional_arrows
from src.visualizations.graph_visuals_layout import _configure_3d_layout, _prepare_layout_config
from src.visualizations.graph_visuals_traces import _create_node_trace, _create_relationship_traces
from src.visualizations.graph_visuals_validation import (
    _validate_filter_parameters,
    _validate_relationship_filters,
    _validate_visualization_data,
)

logger = logging.getLogger(__name__)


def _build_optional_relationship_filters(filter_params: Dict[str, bool]) -> Optional[Dict[str, bool]]:
    """Build relationship filter map unless all relationships are enabled."""
    if filter_params["show_all_relationships"]:
        return None
    relationship_filters = {
        "same_sector": filter_params["show_same_sector"],
        "market_cap_similar": filter_params["show_market_cap"],
        "correlation": filter_params["show_correlation"],
        "corporate_bond_to_equity": filter_params["show_corporate_bond"],
        "commodity_currency": filter_params["show_commodity_currency"],
        "income_comparison": filter_params["show_income_comparison"],
        "regulatory_impact": filter_params["show_regulatory"],
    }
    _validate_relationship_filters(relationship_filters)
    return relationship_filters


def _build_filter_params(
    relationship_options: Optional[Dict[str, bool]],
    toggle_arrows: bool,
    legacy_flags: Optional[Mapping[str, bool]],
) -> Dict[str, bool]:
    """Build and validate full filter parameters with legacy overrides."""
    base_options = {
        "show_same_sector": True,
        "show_market_cap": True,
        "show_correlation": True,
        "show_corporate_bond": True,
        "show_commodity_currency": True,
        "show_income_comparison": True,
        "show_regulatory": True,
        "show_all_relationships": True,
    }
    if relationship_options is not None:
        base_options.update(relationship_options)

    normalized_legacy_flags = dict(legacy_flags or {})
    invalid_keys = sorted(set(normalized_legacy_flags).difference(base_options))
    if invalid_keys:
        logger.error("Unexpected filter options encountered: %s", ", ".join(invalid_keys))
        raise TypeError(f"Unexpected filter options: {', '.join(invalid_keys)}")
    base_options.update(normalized_legacy_flags)

    filter_params = {**base_options, "toggle_arrows": toggle_arrows}
    _validate_filter_parameters(filter_params)
    return filter_params


def visualize_3d_graph(graph: AssetRelationshipGraph) -> go.Figure:
    """Create default 3D visualization with all relationships enabled."""
    return visualize_3d_graph_with_filters(graph)


def visualize_3d_graph_with_filters(
    graph: AssetRelationshipGraph,
    relationship_options: Optional[Dict[str, bool]] = None,
    toggle_arrows: bool = True,
    **legacy_flags: bool,
) -> go.Figure:
    """Create 3D visualization with optional relationship filters."""
    get_visualization_data = getattr(graph, "get_3d_visualization_data_enhanced", None)
    if not isinstance(graph, AssetRelationshipGraph) or not callable(get_visualization_data):
        raise ValueError(
            "graph must be an AssetRelationshipGraph instance with get_3d_visualization_data_enhanced method"
        )

    filter_params = _build_filter_params(relationship_options, toggle_arrows, legacy_flags)

    relationship_filters = _build_optional_relationship_filters(filter_params)

    positions, asset_ids, colors, hover_texts = get_visualization_data()
    _validate_visualization_data(positions, asset_ids, colors, hover_texts)

    fig = go.Figure()
    relationship_traces = _create_relationship_traces(graph, positions, asset_ids, relationship_filters)
    if relationship_traces:
        fig.add_traces(relationship_traces)

    if toggle_arrows:
        arrow_traces = _create_directional_arrows(graph, positions, asset_ids, relationship_filters)
        if arrow_traces:
            fig.add_traces(arrow_traces)

    fig.add_trace(_create_node_trace(positions, asset_ids, colors, hover_texts))
    dynamic_title, options = _prepare_layout_config(len(asset_ids), relationship_traces)
    _configure_3d_layout(fig, dynamic_title, options)
    return fig


__all__ = [
    "REL_TYPE_COLORS",
    "_build_asset_id_index",
    "_build_relationship_index",
    "_create_directional_arrows",
    "_create_relationship_traces",
    "visualize_3d_graph",
    "visualize_3d_graph_with_filters",
]
