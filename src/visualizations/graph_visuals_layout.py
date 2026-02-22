"""
Module for generating dynamic titles and preparing layout configurations
for 3D financial asset network visualizations.

This module provides helper functions to generate dynamic titles,
calculate visible relationships, and prepare layout configurations
for financial asset network plots.
"""

from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go


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
        relationship_traces (List[go.Scatter3d]): Scatter3d traces whose `x` coordinate arrays represent plotted points; traces missing `x` are treated as having zero points.
    
    Returns:
        visible_relationships (int): Estimated number of visible relationships computed by summing all points across traces and dividing the total by 3.
    """
    return sum(len(getattr(t, "x", []) or []) for t in relationship_traces) // 3


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Create a dynamic title from the number of assets and visible relationships and return it together with layout options.
    
    Calculates the number of visible relationships from the provided 3D scatter traces, generates a title by combining that count with the base title and asset count, and returns the title along with the provided layout options (or an empty dict if none were supplied).
    
    Parameters:
        num_assets (int): Number of assets to include in the title.
        relationship_traces (List[go.Scatter3d]): Scatter3d traces used to determine visible relationships.
        base_title (str): Base string to prefix the generated title.
        layout_options (Optional[Dict[str, object]]): Optional layout configuration to return alongside the title.
    
    Returns:
        Tuple[str, Dict[str, object]]: A tuple containing the generated dynamic title and the layout options dictionary (empty if none provided).
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
        scene=dict(
            xaxis=dict(title="Dimension 1", showgrid=True, gridcolor=gridcolor),
            yaxis=dict(title="Dimension 2", showgrid=True, gridcolor=gridcolor),
            zaxis=dict(title="Dimension 3", showgrid=True, gridcolor=gridcolor),
            bgcolor=bgcolor,
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
        ),
        width=width,
        height=height,
        showlegend=True,
        hovermode="closest",
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor=legend_bgcolor,
            bordercolor=legend_bordercolor,
            borderwidth=1,
        ),
    )