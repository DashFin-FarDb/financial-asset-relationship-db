"""
Module for generating dynamic titles and preparing layout configurations
for 3D financial asset network visualizations.

This module provides helper functions to generate dynamic titles,
calculate visible relationships, and prepare layout configurations
for financial asset network plots.
"""

from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go


def _int_option(options: Dict[str, object], key: str, default: int) -> int:
    """Return an int option value with safe fallback to default."""
    value = options.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _str_option(options: Dict[str, object], key: str, default: str) -> str:
    """Return a string option value with safe fallback to default."""
    value = options.get(key, default)
    return value if isinstance(value, str) else default


def _generate_dynamic_title(
    num_assets: int,
    num_relationships: int,
    base_title: str = "Financial Asset Network",
) -> str:
    """
    Builds a title string summarizing the number of assets and relationships for the visualization.

    Returns:
        A title string formatted as "{base_title} - {num_assets} Assets, {num_relationships} Relationships".
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: List[go.Scatter3d]) -> int:
    """
    Estimate the number of visible relationships from a list of 3D scatter traces.

    Parameters:
        relationship_traces (List[go.Scatter3d]):
            Scatter3d traces whose `x` coordinate arrays represent plotted
            points; traces missing `x` are treated as having zero points.

    Returns:
        visible_relationships (int):
            Estimated number of visible relationships computed by summing all
            points across traces and dividing the total by 3.
    """
    return sum(len(getattr(t, "x", []) or []) for t in relationship_traces) // 3


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Create a dynamic title from the number of assets and visible relationships
    and return it together with layout options.

    Calculates the number of visible relationships from the provided 3D scatter
    traces, generates a title by combining that count with the base title and
    asset count, and returns the title along with the provided layout options
    (or an empty dict if none were supplied).

    Parameters:
        num_assets (int): Number of assets to include in the title.
        relationship_traces (List[go.Scatter3d]):
            Scatter3d traces used to determine visible relationships.
        base_title (str): Base string to prefix the generated title.
        layout_options (Optional[Dict[str, object]]):
            Optional layout configuration to return alongside the title.

    Returns:
        Tuple[str, Dict[str, object]]:
            A tuple containing the generated dynamic title and the layout
            options dictionary (empty if none provided).
    """
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(num_assets, num_relationships, base_title)
    return dynamic_title, layout_options or {}


def _configure_3d_layout(
    fig: go.Figure,
    title: str,
    options: Optional[Dict[str, object]] = None,
) -> None:
    """Apply 3D scene layout to *fig*.

    Supported *options* keys: width, height, gridcolor, bgcolor,
    legend_bgcolor, legend_bordercolor.
    """
    opts = options or {}
    width = _int_option(opts, "width", 1200)
    height = _int_option(opts, "height", 800)
    gridcolor = _str_option(opts, "gridcolor", "rgba(200, 200, 200, 0.3)")
    bgcolor = _str_option(opts, "bgcolor", "rgba(248, 248, 248, 0.95)")
    legend_bgcolor = _str_option(opts, "legend_bgcolor", "rgba(255, 255, 255, 0.8)")
    legend_bordercolor = _str_option(opts, "legend_bordercolor", "rgba(0, 0, 0, 0.3)")

    fig.update_layout(
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 16},
        },
        scene={
            "xaxis": {"title": "Dimension 1", "showgrid": True, "gridcolor": gridcolor},
            "yaxis": {"title": "Dimension 2", "showgrid": True, "gridcolor": gridcolor},
            "zaxis": {"title": "Dimension 3", "showgrid": True, "gridcolor": gridcolor},
            "bgcolor": bgcolor,
            "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 1.5}},
        },
        width=width,
        height=height,
        showlegend=True,
        hovermode="closest",
        legend={
            "x": 0.02,
            "y": 0.98,
            "bgcolor": legend_bgcolor,
            "bordercolor": legend_bordercolor,
            "borderwidth": 1,
        },
    )
