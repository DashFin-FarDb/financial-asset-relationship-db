"""Metric visualization helpers for asset relationship analytics."""

from datetime import datetime
from typing import Tuple

import plotly.graph_objects as go  # type: ignore[import-untyped]

from src.logic.asset_graph import AssetRelationshipGraph

_BASE_COLORS = ["blue", "green", "orange", "red", "purple"]


def _asset_class_distribution(distribution: dict) -> go.Figure:
    """
    Create a bar chart of asset class counts.

    Parameters:
        distribution (dict): Mapping of asset class names to integer counts.

    Returns:
        go.Figure: Plotly Figure containing a bar trace with asset class names on the x-axis and counts on the y-axis.
    """
    classes = list(distribution.keys())
    counts = list(distribution.values())
    colors = [_BASE_COLORS[i % len(_BASE_COLORS)] for i in range(len(classes))]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=classes, y=counts, marker_color=colors))
    _apply_asset_class_layout(fig)
    return fig


def _apply_asset_class_layout(fig: go.Figure) -> None:
    """
    Set titles and axis labels for an asset class distribution figure.

    Modifies the provided Plotly Figure in place to set the chart title to "Asset Class Distribution", the x-axis title to "Asset Class", and the y-axis title to "Count".

    Parameters:
        fig (go.Figure): Figure whose layout will be updated in place.
    """
    fig.update_layout(
        title="Asset Class Distribution",
        xaxis_title="Asset Class",
        yaxis_title="Count",
    )


def _relationship_distribution(distribution: dict) -> go.Figure:
    """
    Creates a bar chart of counts per relationship type.

    Parameters:
        distribution (dict): Mapping of relationship type names (str) to counts (int).

    Returns:
        go.Figure: Plotly Figure with relationship types on the x-axis and counts on the y-axis.
    """
    rel_types = list(distribution.keys())
    rel_counts = list(distribution.values())
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rel_types, y=rel_counts, marker_color="lightblue"))
    _apply_relationship_layout(fig)
    return fig


def _apply_relationship_layout(fig: go.Figure) -> None:
    """
    Apply a consistent layout for a relationship-type distribution chart.

    Updates the provided figure in place by setting the title to "Relationship Types Distribution", the x-axis title to "Relationship Type", the y-axis title to "Count", and rotating x-axis tick labels by -45 degrees.
    """
    fig.update_layout(
        title="Relationship Types Distribution",
        xaxis_title="Relationship Type",
        yaxis_title="Count",
        xaxis_tickangle=-45,
    )


def _regulatory_events_timeline(events: list) -> go.Figure:
    """
    Create a timeline bar chart of regulatory events showing impact scores over time.

    Each event object must provide:
    - date: ISO 8601 date string
    - asset_id: identifier used in bar labels
    - event_type.value: label text for the event type
    - impact_score: numeric value plotted on the y axis

    Parameters:
        events (list): Sequence of event objects with the fields described above.

    Returns:
        go.Figure: Plotly figure with dates on the x axis and impact scores on the y axis. Bars are labeled as "asset_id: event_type.value" and colored green for impact_score > 0, red otherwise.
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
    _apply_regulatory_events_layout(fig)
    return fig


def _apply_regulatory_events_layout(fig: go.Figure) -> None:
    """
    Apply layout settings for the regulatory events timeline figure.

    Sets the figure title to "Regulatory Events Timeline", the x-axis title to "Date", and the y-axis title to "Impact Score" in place.
    """
    fig.update_layout(
        title="Regulatory Events Timeline",
        xaxis_title="Date",
        yaxis_title="Impact Score",
    )


def visualize_metrics(
    graph: AssetRelationshipGraph,
) -> Tuple[go.Figure, go.Figure, go.Figure]:
    """
    Build three Plotly figures summarizing metrics extracted from an AssetRelationshipGraph.

    Parameters:
        graph (AssetRelationshipGraph): Source graph whose metrics and regulatory events are used to create the figures.

    Returns:
        asset_class_fig (go.Figure): Bar chart showing counts per asset class.
        relationship_fig (go.Figure): Bar chart showing counts per relationship type.
        regulatory_timeline_fig (go.Figure): Timeline bar chart of regulatory events with impact scores.
    """
    metrics = graph.calculate_metrics()
    return (
        _asset_class_distribution(metrics["asset_class_distribution"]),
        _relationship_distribution(metrics["relationship_distribution"]),
        _regulatory_events_timeline(graph.regulatory_events),
    )
