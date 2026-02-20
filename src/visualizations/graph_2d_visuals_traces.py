from typing import Dict, List, Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals_constants import (
    ASSET_CLASS_COLORS,
    REL_TYPE_COLORS,
)


def _create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    show_same_sector: bool = True,
    show_market_cap: bool = True,
    show_correlation: bool = True,
    show_corporate_bond: bool = True,
    show_commodity_currency: bool = True,
    show_income_comparison: bool = True,
    show_regulatory: bool = True,
    show_all_relationships: bool = False,
) -> List[go.Scatter]:
    """
    Builds Plotly line traces representing relationships between the specified assets.

    Filters relationships from the provided graph according to the boolean flags and groups them by relationship type. Each returned trace contains line segments connecting asset positions and hover text showing "source → target", relationship type, and numeric strength.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing assets and their relationships.
        positions (Dict[str, Tuple[float, float]]): Mapping from asset ID to (x, y) coordinates.
        asset_ids (List[str]): Asset IDs to include; order is preserved for node layout.
        show_same_sector (bool): Include "same_sector" relationships when True.
        show_market_cap (bool): Include "market_cap_similar" relationships when True.
        show_correlation (bool): Include "correlation" relationships when True.
        show_corporate_bond (bool): Include "corporate_bond_to_equity" relationships when True.
        show_commodity_currency (bool): Include "commodity_currency" relationships when True.
        show_income_comparison (bool): Include "income_comparison" relationships when True.
        show_regulatory (bool): Include "regulatory_impact" relationships when True.
        show_all_relationships (bool): When True, ignore the individual relationship flags and include all relationships present in the graph.

    Returns:
        List[go.Scatter]: A list of Plotly Scatter traces (mode="lines"), one per relationship type present, each containing line segments and hover text for its edges.
    """
    if not asset_ids or not positions:
        return []

    relationship_filters = {
        "same_sector": show_same_sector,
        "market_cap_similar": show_market_cap,
        "correlation": show_correlation,
        "corporate_bond_to_equity": show_corporate_bond,
        "commodity_currency": show_commodity_currency,
        "income_comparison": show_income_comparison,
        "regulatory_impact": show_regulatory,
    }

    asset_id_set = set(asset_ids)
    relationship_groups: Dict[str, list] = {}

    for source_id in asset_ids:
        if source_id not in graph.relationships:
            continue
        for target_id, rel_type, strength in graph.relationships[source_id]:
            if target_id not in positions or target_id not in asset_id_set:
                continue
            if (
                not show_all_relationships
                and rel_type in relationship_filters
                and not relationship_filters[rel_type]
            ):
                continue
            relationship_groups.setdefault(rel_type, []).append(
                {"source_id": source_id, "target_id": target_id, "strength": strength}
            )

    traces = []
    for rel_type, relationships in relationship_groups.items():
        edges_x, edges_y, hover_texts = [], [], []
        for rel in relationships:
            sx, sy = positions[rel["source_id"]]
            tx, ty = positions[rel["target_id"]]
            edges_x.extend([sx, tx, None])
            edges_y.extend([sy, ty, None])
            hover = (
                f"{rel['source_id']} → {rel['target_id']}<br>"
                f"Type: {rel_type}<br>"
                f"Strength: {rel['strength']:.2f}"
            )
            hover_texts.extend([hover, hover, None])

        traces.append(
            go.Scatter(
                x=edges_x,
                y=edges_y,
                mode="lines",
                line=dict(color=REL_TYPE_COLORS.get(rel_type, "#888888"), width=2),
                hovertext=hover_texts,
                hoverinfo="text",
                name=rel_type.replace("_", " ").title(),
                showlegend=True,
            )
        )

    return traces


def _create_node_trace(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
) -> go.Scatter:
    """
    Create a Plotly scatter trace representing asset nodes positioned in 2D.

    Each node's color is derived from its asset class via ASSET_CLASS_COLORS (falls back to "#7f7f7f"), and its marker size is 20 plus up to 30 additional units based on the asset's number of outgoing relationships (5 units per connection, capped at +30). Hover text shows the asset ID and its class.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing assets and their relationships.
        positions (Dict[str, Tuple[float, float]]): Mapping from asset ID to (x, y) coordinates.
        asset_ids (List[str]): Ordered list of asset IDs to include in the trace.

    Returns:
        go.Scatter: A scatter trace with markers and labels for the specified assets.
    """
    node_x = [positions[a][0] for a in asset_ids]
    node_y = [positions[a][1] for a in asset_ids]
    colors, hover_texts, node_sizes = [], [], []

    for asset_id in asset_ids:
        asset = graph.assets[asset_id]
        asset_class = (
            asset.asset_class.value
            if hasattr(asset.asset_class, "value")
            else str(asset.asset_class)
        )
        colors.append(ASSET_CLASS_COLORS.get(asset_class.lower(), "#7f7f7f"))
        hover_texts.append(f"{asset_id}<br>Class: {asset_class}")
        num_connections = len(graph.relationships.get(asset_id, []))
        node_sizes.append(20 + min(num_connections * 5, 30))

    return go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(
            size=node_sizes,
            color=colors,
            opacity=0.9,
            line=dict(color="rgba(0,0,0,0.8)", width=2),
        ),
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont=dict(size=10, color="black"),
        name="Assets",
        showlegend=False,
    )
