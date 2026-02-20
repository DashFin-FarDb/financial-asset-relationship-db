from datetime import datetime
from typing import List, Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph

_BASE_COLORS = ["blue", "green", "orange", "red", "purple"]


def _asset_class_distribution(distribution: dict) -> go.Figure:
    """Creates a bar chart for asset class distribution.

    Args:
        distribution (dict): A dictionary with asset classes as keys and their counts as values.

    Returns:
        go.Figure: A Plotly figure object representing the asset class distribution.
    """
    classes = list(distribution.keys())
    counts = list(distribution.values())
    colors = [_BASE_COLORS[i % len(_BASE_COLORS)] for i in range(len(classes))]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=classes, y=counts, marker_color=colors))
    fig.update_layout(
        title="Asset Class Distribution",
        xaxis_title="Asset Class",
        yaxis_title="Count",
    )
    return fig


def _relationship_distribution(distribution: dict) -> go.Figure:
    """Creates a bar chart for relationship types distribution.

    Args:
        distribution (dict): A dictionary with relationship types as keys and their counts as values.

    Returns:
        go.Figure: A Plotly figure object representing the bar chart.
    """
    rel_types = list(distribution.keys())
    rel_counts = list(distribution.values())
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rel_types, y=rel_counts, marker_color="lightblue"))
    fig.update_layout(
        title="Relationship Types Distribution",
        xaxis_title="Relationship Type",
        yaxis_title="Count",
        xaxis_tickangle=-45,
    )
    return fig


def _regulatory_events_timeline(events: list) -> go.Figure:
    """Generate a timeline of regulatory events as a bar chart.

    This function takes a list of regulatory events, sorts them by date,  and
    constructs a bar chart displaying the impact scores of each event.  It extracts
    the dates, names, and impact scores from the sorted events  and uses Plotly's
    graphing library to create a visually informative  representation of the
    regulatory timeline.

    Args:
        events (list): A list of regulatory event objects containing date,
            asset_id, event_type, and impact_score attributes.
    """
    sorted_events = sorted(events, key=lambda e: datetime.fromisoformat(e.date))
    dates = [datetime.fromisoformat(e.date) for e in sorted_events]
    names = [f"{e.asset_id}: {e.event_type.value}" for e in sorted_events]
    impacts = [e.impact_score for e in sorted_events]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=dates,
            y=impacts,
            name="Impact Score",
            text=names,
            textposition="outside",
            marker_color=["green" if x > 0 else "red" for x in impacts],
        )
    )
    fig.update_layout(
        title="Regulatory Events Timeline",
        xaxis_title="Date",
        yaxis_title="Impact Score",
    )
    return fig


def visualize_metrics(
    graph: AssetRelationshipGraph,
) -> Tuple[go.Figure, go.Figure, go.Figure]:
    """Create visualizations of graph metrics."""
    metrics = graph.calculate_metrics()
    return (
        _asset_class_distribution(metrics["asset_class_distribution"]),
        _relationship_distribution(metrics["relationship_distribution"]),
        _regulatory_events_timeline(graph.regulatory_events),
    )
