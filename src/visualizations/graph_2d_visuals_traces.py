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
    """Create 2D relationship traces for a given asset relationship graph.

    This function generates visual traces representing relationships between
    assets based on various filters. It processes the input `graph` to identify
    relationships between `asset_ids` and their corresponding `positions`,
    applying filters for different relationship types. The resulting traces are
    formatted for visualization, including hover information for each
    relationship.

    Args:
        graph (AssetRelationshipGraph): The graph containing asset relationships.
        positions (Dict[str, Tuple[float, float]]):
            A dictionary mapping asset IDs to their 2D positions.
        asset_ids (List[str]): A list of asset IDs to include in the traces.
        show_same_sector (bool):
            Flag to show relationships within the same sector. Defaults to True.
        show_market_cap (bool):
            Flag to show relationships based on market
            capitalization. Defaults to True.
        show_correlation (bool):
            Flag to show correlation relationships.
            Defaults to True.
        show_corporate_bond(bool):
            Flag to show corporate bond relationships.
            Defaults to True.
        show_commodity_currency(bool):
            Flag to show commodity currency relationships.
            Defaults to True.
        show_income_comparison(bool):
            Flag to show income comparison relationships.
            Defaults to True.
        show_regulatory(bool):
            Flag to show regulatory impact relationships.
            Defaults to True.
        show_all_relationships(bool):
            Flag to show all relationships regardless of type.
            Defaults to False.

    Returns:
        List[go.Scatter]: A list of scatter traces representing the
            relationships.
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
            )
        )

    return traces


def _create_node_trace(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
) -> go.Scatter:
    """Create a scatter plot trace for asset nodes.

    This function generates a scatter plot trace using the provided asset
    positions and their corresponding asset IDs. It retrieves the asset classes
    to determine the colors for each node and calculates the node sizes based on
    the number of connections each asset has. The resulting trace is suitable for
    visualization in a graphing library.

    Args:
        graph(AssetRelationshipGraph): The graph containing asset relationships.
        positions(Dict[str, Tuple[float, float]]): A dictionary mapping asset IDs to
            their(x, y) positions.
        asset_ids(List[str]): A list of asset IDs to be included in the trace.
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
