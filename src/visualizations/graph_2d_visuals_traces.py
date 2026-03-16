"""Trace-construction helpers for 2D graph visualizations."""

from typing import Dict, List, Tuple, TypedDict

import plotly.graph_objects as go

from src.logic.asset_graph import AssetRelationshipGraph
from src.visualizations.graph_2d_visuals_constants import (
    ASSET_CLASS_COLORS,
    REL_TYPE_COLORS,
)


class RelationshipTraceOptions(TypedDict, total=False):
    """Optional visibility toggles for relationship traces."""

    show_same_sector: bool
    show_market_cap: bool
    show_correlation: bool
    show_corporate_bond: bool
    show_commodity_currency: bool
    show_income_comparison: bool
    show_regulatory: bool
    show_all_relationships: bool


DEFAULT_TRACE_OPTIONS: Dict[str, bool] = {
    "show_same_sector": True,
    "show_market_cap": True,
    "show_correlation": True,
    "show_corporate_bond": True,
    "show_commodity_currency": True,
    "show_income_comparison": True,
    "show_regulatory": True,
    "show_all_relationships": False,
}


def create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    *,
    options: RelationshipTraceOptions | None = None,
    **legacy_flags: bool,
) -> List[go.Scatter]:
    """Public API for building 2D relationship traces.

    The preferred API is the `options` mapping. Legacy keyword flags are still
    accepted for backward compatibility and override `options` values when set.
    """
    normalized_options = _resolve_trace_options(options, legacy_flags)
    return _create_2d_relationship_traces(
        graph=graph,
        positions=positions,
        asset_ids=asset_ids,
        options=normalized_options,
    )


def _create_2d_relationship_traces(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    options: Dict[str, bool] | None = None,
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
        options (Dict[str, bool] | None):
            Optional visibility toggles. Missing keys fall back to defaults.

    Returns:
        List[go.Scatter]: A list of scatter traces representing the
            relationships.
    """
    if not asset_ids or not positions:
        return []

    normalized_options = _resolve_trace_options(options, {})
    relationship_filters = _build_relationship_filters(normalized_options)
    relationship_groups = _collect_relationship_groups(
        graph=graph,
        positions=positions,
        asset_ids=asset_ids,
        relationship_filters=relationship_filters,
        show_all_relationships=normalized_options["show_all_relationships"],
    )
    return [
        _build_relationship_trace(rel_type, relationships, positions)
        for rel_type, relationships in relationship_groups.items()
    ]


def _resolve_trace_options(
    options: Dict[str, bool] | None,
    legacy_flags: Dict[str, bool],
) -> Dict[str, bool]:
    """Merge defaults, options, and legacy flags into one mapping."""
    resolved = dict(DEFAULT_TRACE_OPTIONS)
    if options:
        resolved.update(options)
    if legacy_flags:
        resolved.update(legacy_flags)
    return resolved


def _build_relationship_filters(options: Dict[str, bool]) -> Dict[str, bool]:
    """Build map of relationship-type visibility toggles."""
    return {
        "same_sector": options["show_same_sector"],
        "market_cap_similar": options["show_market_cap"],
        "correlation": options["show_correlation"],
        "corporate_link": options["show_corporate_bond"],
        "commodity_currency": options["show_commodity_currency"],
        "income_comparison": options["show_income_comparison"],
        "event_impact": options["show_regulatory"],
    }


def _collect_relationship_groups(
    *,
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
    relationship_filters: Dict[str, bool],
    show_all_relationships: bool,
) -> Dict[str, list[Dict[str, object]]]:
    """Collect relationships grouped by relationship type."""
    asset_id_set = set(asset_ids)
    relationship_groups: Dict[str, list[Dict[str, object]]] = {}
    for source_id in asset_ids:
        for target_id, rel_type, strength in graph.relationships.get(source_id, []):
            if target_id not in positions or target_id not in asset_id_set:
                continue
            if _relationship_hidden(
                rel_type=rel_type,
                relationship_filters=relationship_filters,
                show_all_relationships=show_all_relationships,
            ):
                continue
            relationship_groups.setdefault(rel_type, []).append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "strength": strength,
                }
            )
    return relationship_groups


def _relationship_hidden(
    *,
    rel_type: str,
    relationship_filters: Dict[str, bool],
    show_all_relationships: bool,
) -> bool:
    """Return True when a relationship type should be hidden."""
    return (
        not show_all_relationships
        and rel_type in relationship_filters
        and not relationship_filters[rel_type]
    )


def _build_relationship_trace(
    rel_type: str,
    relationships: list[Dict[str, object]],
    positions: Dict[str, Tuple[float, float]],
) -> go.Scatter:
    """Build one Plotly trace for a relationship type."""
    edges_x: list[float | None] = []
    edges_y: list[float | None] = []
    hover_texts: list[str | None] = []
    for rel in relationships:
        source_id = str(rel["source_id"])
        target_id = str(rel["target_id"])
        strength = float(rel.get("strength", 0.0))
        sx, sy = positions[source_id]
        tx, ty = positions[target_id]
        edges_x.extend([sx, tx, None])
        edges_y.extend([sy, ty, None])
        hover_text = (
            f"{source_id} → {target_id}<br>"
            f"Type: {rel_type}<br>"
            f"Strength: {strength:.2f}"
        )
        hover_texts.extend([hover_text, hover_text, None])
    return go.Scatter(
        x=edges_x,
        y=edges_y,
        mode="lines",
        line={"color": REL_TYPE_COLORS.get(rel_type, "#888888"), "width": 2},
        hovertext=hover_texts,
        hoverinfo="text",
    )


def _create_node_trace(
    graph: AssetRelationshipGraph,
    positions: Dict[str, Tuple[float, float]],
    asset_ids: List[str],
) -> go.Scatter:
    """Create a scatter plot trace for asset nodes.

    This function generates a scatter plot trace using the provided asset
    positions and their corresponding asset IDs. It retrieves the
    asset classes to determine the colors for each node and calculates
    node sizes based on the number of connections each asset has.
    The resulting trace is suitable for visualization in a graphing
    library.

    Args:
        graph(AssetRelationshipGraph): The graph containing
            asset relationships.
        positions(Dict[str, Tuple[float, float]]):
            A dictionary mapping asset IDs to their(x, y) positions.
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
        colors.append(
            ASSET_CLASS_COLORS.get(asset_class.lower(), "#7f7f7f")
        )
        hover_texts.append(f"{asset_id}<br>Class: {asset_class}")
        num_connections = len(
            graph.relationships.get(asset_id, [])
        )
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
