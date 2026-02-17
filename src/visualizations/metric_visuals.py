from datetime import datetime
from typing import Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph


def visualize_metrics(
    graph: AssetRelationshipGraph,
) -> Tuple[go.Figure, go.Figure, go.Figure]:
    """Create visualizations of graph metrics"""
    metrics = graph.calculate_metrics()

    # Asset class distribution
    fig1 = go.Figure()
    classes = list(metrics["asset_class_distribution"].keys())
    counts = list(metrics["asset_class_distribution"].values())
    # Color consistency with 5 classes; fallback if fewer
    base_colors = ["blue", "green", "orange", "red", "purple"]
    bar_colors = [base_colors[i % len(base_colors)] for i in range(len(classes))]
    fig1.add_trace(go.Bar(x=classes, y=counts, marker_color=bar_colors))
    fig1.update_layout(
        title="Asset Class Distribution",
        xaxis_title="Asset Class",
        yaxis_title="Count",
    )

    # Relationship types distribution
    fig2 = go.Figure()
    rel_types = list(metrics["relationship_distribution"].keys())
    rel_counts = list(metrics["relationship_distribution"].values())
    fig2.add_trace(go.Bar(x=rel_types, y=rel_counts, marker_color="lightblue"))
    fig2.update_layout(
        title="Relationship Types Distribution",
        xaxis_title="Relationship Type",
        yaxis_title="Count",
        xaxis_tickangle=-45,
    )

    # Regulatory events timeline (sorted by date and using datetime)
    fig3 = go.Figure()
    events = sorted(
        graph.regulatory_events,
        key=lambda e: datetime.fromisoformat(e.date),
    )
    event_dates = [datetime.fromisoformat(e.date) for e in events]
    event_names = [f"{e.asset_id}: {e.event_type.value}" for e in events]
    event_impacts = [e.impact_score for e in events]

    fig3.add_trace(
        go.Bar(
            x=event_dates,
            y=event_impacts,
            name="Impact Score",
            text=event_names,
            textposition="outside",
            marker_color=["green" if x > 0 else "red" for x in event_impacts],
        )
    )
    fig3.update_layout(
        title="Regulatory Events Timeline",
        xaxis_title="Date",
        yaxis_title="Impact Score",
    )

    return fig1, fig2, fig3
