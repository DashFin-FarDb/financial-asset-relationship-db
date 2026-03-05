from typing import Dict, List, Tuple

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals_constants import (
    ASSET_CLASS_COLORS,
    REL_TYPE_COLORS,
)


def _should_include_relationship(
    target_id: str,
    positions: Dict[str, Tuple[float, float]],
    asset_id_set: set[str],
    relationship_enabled: bool,
) -> bool:
    """Return True when a relationship should be included in traces."""
    if target_id not in positions or target_id not in asset_id_set:
        return False
    return relationship_enabled


def _collect_relationship_groups(
    graph: AssetRelationshipGraph,
    asset_ids: List[str],
    positions: Dict[str, Tuple[float, float]],
    relationship_filters: Dict[str, bool] | None,
) -> Dict[str, list]:
    """Group relationships by type after applying display filters."""
    asset_id_set = set(asset_ids)
    relationship_groups: Dict[str, list] = {}

    for source_id in asset_ids:
        source_relationships = graph.relationships.get(source_id, [])
        for target_id, rel_type, strength in source_relationships:
            relationship_enabled = True if relationship_filters is None else relationship_filters.get(rel_type, True)
            if not _should_include_relationship(
                target_id,
                positions,
                asset_id_set,
                relationship_enabled,
            ):
                continue
            relationship_groups.setdefault(rel_type, []).append(
                {"source_id": source_id, "target_id": target_id, "strength": strength}
            )

    return relationship_groups


def _build_relationship_trace(
    rel_type: str,
    relationships: list[dict[str, object]],
    positions: Dict[str, Tuple[float, float]],
) -> go.Scatter:
    """Build one Plotly line trace for a relationship type."""
    edges_x, edges_y, hover_texts = [], [], []
    for rel in relationships:
        source_id = str(rel["source_id"])
        target_id = str(rel["target_id"])
        strength = float(rel["strength"])
        sx, sy = positions[source_id]
        tx, ty = positions[target_id]
        edges_x.extend([sx, tx, None])
        edges_y.extend([sy, ty, None])
        hover = f"{source_id} → {target_id}<br>" f"Type: {rel_type}<br>" f"Strength: {strength:.2f}"
        hover_texts.extend([hover, hover, None])

    return go.Scatter(
        x=edges_x,
        y=edges_y,
        mode="lines",
        line={"color": REL_TYPE_COLORS.get(rel_type, "#888888"), "width": 2},
    )


def _create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    relationship_filters: Dict[str, bool] | None = None,
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
        relationship_filters (Dict[str, bool] | None):
            Optional map of relationship type -> enabled/disabled.
            When None, defaults to enabling all known relationship types.
        relationship_filters=None means all relationship types are shown.

    Returns:
        List[go.Scatter]: A list of scatter traces representing the
            relationships.
    """
    if not asset_ids or not positions:
        return []

    if relationship_filters is None:
        relationship_filters = {
            "same_sector": True,
            "market_cap_similar": True,
            "correlation": True,
            "corporate_link": True,
            "commodity_currency": True,
            "income_comparison": True,
            "event_impact": True,
        }

    relationship_groups = _collect_relationship_groups(
        graph,
        asset_ids,
        positions,
        relationship_filters,
    )

    traces: List[go.Scatter] = []
    for rel_type, relationships in relationship_groups.items():
        traces.append(
            _build_relationship_trace(
                rel_type,
                relationships,
                positions,
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
        asset_class = asset.asset_class.value if hasattr(asset.asset_class, "value") else str(asset.asset_class)
        colors.append(ASSET_CLASS_COLORS.get(asset_class.lower(), "#7f7f7f"))
        hover_texts.append(f"{asset_id}<br>Class: {asset_class}")
        num_connections = len(graph.relationships.get(asset_id, []))
        node_sizes.append(20 + min(num_connections * 5, 30))

    return go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker={
            "size": node_sizes,
            "color": colors,
            "opacity": 0.9,
            "line": {"color": "rgba(0,0,0,0.8)", "width": 2},
        },
        text=asset_ids,
        hovertext=hover_texts,
        hoverinfo="text",
        textposition="top center",
        textfont={"size": 10, "color": "black"},
        name="Assets",
        showlegend=False,
    )
