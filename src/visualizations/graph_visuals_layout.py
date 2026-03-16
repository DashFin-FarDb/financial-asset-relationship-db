"""
Module for generating dynamic titles and preparing layout configurations
for 3D financial asset network visualizations.

This module provides helper functions to generate dynamic titles,
calculate visible relationships, and prepare layout configurations
for financial asset network plots.
"""

from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go  # type: ignore[import-untyped]


def _generate_dynamic_title(
    num_assets: int,
    num_relationships: int,
    base_title: str = "Financial Asset Network",
) -> str:
    """
    Build a title summarizing asset and relationship counts.

    Returns:
        A title string formatted as
        "{base_title} - {num_assets} Assets, {num_relationships} Relationships".
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(
    relationship_traces: List[go.Scatter3d],
) -> int:
    """
    Estimate the number of visible relationships represented by a list of 3D scatter traces.
    
    Parameters:
        relationship_traces (List[go.Scatter3d]): Scatter3d traces whose `x` coordinate arrays represent plotted points; traces missing `x` or with empty `x` are treated as having zero points.
    
    Returns:
        int: Estimated number of visible relationships, computed as the total plotted points across all traces divided by 3.
    """
    total_points = sum(len(getattr(trace, "x", []) or []) for trace in relationship_traces)
    return total_points // 3


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Generate a title summarizing asset and visible relationship counts and return it alongside layout options.
    
    Estimates the number of visible relationships from the provided 3D traces, composes a dynamic title using the asset and relationship counts with the given base title, and returns that title together with the provided layout options.
    
    Parameters:
        num_assets (int): Number of assets to include in the title.
        relationship_traces (List[go.Scatter3d]): Scatter3d traces used to estimate visible relationships.
        base_title (str): Base string to prefix the generated title.
        layout_options (Optional[Dict[str, object]]): Optional layout configuration to return with the title.
    
    Returns:
        Tuple[str, Dict[str, object]]: The generated title and the layout options dictionary (empty dict if none provided).
    """
    num_relationships = _calculate_visible_relationships(relationship_traces)
    dynamic_title = _generate_dynamic_title(
        num_assets,
        num_relationships,
        base_title,
    )
    return dynamic_title, layout_options or {}


def _configure_3d_layout(
    fig: go.Figure,
    title: str,
    options: Optional[Dict[str, object]] = None,
) -> None:
    """
    Apply a 3D scene layout and visual defaults to a Plotly Figure.
    
    Parameters:
        fig (go.Figure): Figure to update; modified in place.
        title (str): Text to set as the figure title.
        options (dict, optional): Layout overrides. Supported keys:
            - width (int): Figure width in pixels. Default 1200.
            - height (int): Figure height in pixels. Default 800.
            - gridcolor (str): Color for axis grid lines. Default "rgba(200, 200, 200, 0.3)".
            - bgcolor (str): 3D scene background color. Default "rgba(248, 248, 248, 0.95)".
            - legend_bgcolor (str): Legend background color. Default "rgba(255, 255, 255, 0.8)".
            - legend_bordercolor (str): Legend border color. Default "rgba(0, 0, 0, 0.3)".
    """
    opts = options or {}
    width = int(opts.get("width", 1200))
    height = int(opts.get("height", 800))
    gridcolor = str(opts.get("gridcolor", "rgba(200, 200, 200, 0.3)"))
    bgcolor = str(opts.get("bgcolor", "rgba(248, 248, 248, 0.95)"))
    legend_bgcolor = str(opts.get("legend_bgcolor", "rgba(255, 255, 255, 0.8)"))
    legend_bordercolor = str(opts.get("legend_bordercolor", "rgba(0, 0, 0, 0.3)"))

    fig.update_layout(
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 16},
        },
        scene={
            "xaxis": {
                "title": "Dimension 1",
                "showgrid": True,
                "gridcolor": gridcolor,
            },
            "yaxis": {
                "title": "Dimension 2",
                "showgrid": True,
                "gridcolor": gridcolor,
            },
            "zaxis": {
                "title": "Dimension 3",
                "showgrid": True,
                "gridcolor": gridcolor,
            },
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
