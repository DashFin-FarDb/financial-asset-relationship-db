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
    Generate a dynamic title string for the network visualization.

    Constructs a title using the number of assets and relationships,
    with an optional base title prefix.
    """
    return f"{base_title} - {num_assets} Assets, {num_relationships} Relationships"


def _calculate_visible_relationships(relationship_traces: List[go.Scatter3d]) -> int:
    """
    Calculate the number of visible relationships.

    Counts the total number of points across all provided Scatter3d traces
    and estimates the number of relationships by dividing by 3.
    """
    return sum(len(getattr(t, "x", []) or []) for t in relationship_traces) // 3


def _prepare_layout_config(
    num_assets: int,
    relationship_traces: List[go.Scatter3d],
    base_title: str = "Financial Asset Network",
    layout_options: Optional[Dict[str, object]] = None,
) -> Tuple[str, Dict[str, object]]:
    """
    Prepare layout configuration for the visualization.

    Calculates a dynamic title based on the number of assets and relationships
    and returns it alongside layout options, using defaults if none are provided.
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
