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
    """
    Builds Plotly 2D line traces representing relationships between assets.

    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph containing assets and their relationships.
        positions (Dict[str, Tuple[float, float]]): Mapping of asset ID to (x, y) coordinates.
        asset_ids (List[str]): Ordered list of asset IDs to include in traces.
        options (RelationshipTraceOptions | None): Optional mapping of per-relationship-type visibility flags; preferred API.
        **legacy_flags (bool): Legacy per-relationship boolean flags accepted for backward compatibility; when present they override values in `options`.

    Returns:
        List[go.Scatter]: A list of Plotly Scatter traces (one per visible relationship type). Returns an empty list if `asset_ids` or `positions` are empty.
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
    """
    Builds Plotly line traces representing relationships between the provided assets.

    Each returned trace groups all relationships of a single type and contains segmented lines between asset coordinates with hover text showing source, target, relationship type, and strength.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing assets and their relationships.
        positions (Dict[str, Tuple[float, float]]): Mapping of asset IDs to (x, y) coordinates.
        asset_ids (List[str]): Ordered list of asset IDs to include; only relationships between these and assets present in `positions` are considered.
        options (Dict[str, bool] | None): Optional visibility toggles per high-level option; missing keys fall back to DEFAULT_TRACE_OPTIONS.

    Returns:
        List[go.Scatter]: A list of Scatter traces, one per relationship type present. Returns an empty list if `asset_ids` or `positions` is empty.
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
    """
    Resolve trace option flags by merging module defaults, `options`, and `legacy_flags` in that precedence order.

    Parameters:
        options (dict[str, bool] | None): Optional overrides for default flags.
        legacy_flags (dict[str, bool]): Legacy overrides that take highest precedence over `options` and defaults.

    Returns:
        dict[str, bool]: A mapping of option names to booleans where values from `legacy_flags` override `options`, which override the module defaults.
    """
    resolved = dict(DEFAULT_TRACE_OPTIONS)
    if options:
        resolved.update(options)
    if legacy_flags:
        resolved.update(legacy_flags)
    return resolved


def _build_relationship_filters(options: Dict[str, bool]) -> Dict[str, bool]:
    """
    Create a normalized mapping from high-level visibility options to relationship-type filter flags.

    Parameters:
        options (Dict[str, bool]): Visibility options expected to include keys:
            `show_same_sector`, `show_market_cap`, `show_correlation`,
            `show_corporate_bond`, `show_commodity_currency`,
            `show_income_comparison`, `show_regulatory`.

    Returns:
        Dict[str, bool]: Mapping of normalized relationship-type keys to visibility flags:
            `same_sector`, `market_cap_similar`, `correlation`, `corporate_link`,
            `commodity_currency`, `income_comparison`, `event_impact`.
    """
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
    """
    Group visible relationships from the graph by relationship type for the given assets and positions.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing assets and their relationships.
        positions (Dict[str, Tuple[float, float]]): Mapping of asset IDs to 2D positions; only relationships whose target appears in this mapping are considered.
        asset_ids (List[str]): Ordered list of asset IDs to iterate as sources; only relationships with targets also in this list are considered.
        relationship_filters (Dict[str, bool]): Visibility toggles keyed by relationship type; a relationship is excluded when its type is present and set to False, unless show_all_relationships is True.
        show_all_relationships (bool): If True, ignore relationship_filters and include all relationship types.

    Returns:
        Dict[str, list[Dict[str, object]]]: Mapping from relationship type to a list of relationship records. Each record contains:
            - "source_id" (str): ID of the source asset.
            - "target_id" (str): ID of the target asset.
            - "strength" (object): Relationship strength value (as provided by the graph).
    """
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
    """
    Determine whether a relationship type should be hidden given the active filters and the global show-all flag.

    Parameters:
        relationship_filters (Dict[str, bool]): Mapping from relationship type name to a boolean indicating whether that type is enabled.
        show_all_relationships (bool): Global override; when True all relationship types are shown regardless of individual filters.

    Returns:
        bool: `True` if the relationship should be hidden, `False` otherwise.
    """
    return not show_all_relationships and rel_type in relationship_filters and not relationship_filters[rel_type]


def _build_relationship_trace(
    rel_type: str,
    relationships: list[Dict[str, object]],
    positions: Dict[str, Tuple[float, float]],
) -> go.Scatter:
    """
    Construct a Plotly Scatter trace containing one independent line segment per relationship.

    Each segment connects the source and target coordinates and carries hover text showing
    "{source} → {target}", the relationship type, and the numeric strength formatted to two decimals.

    Parameters:
        rel_type (str): Relationship category label used in hover text and to select the segment color.
        relationships (list[Dict[str, object]]): Records with keys "source_id", "target_id", and optional
            numeric "strength".
        positions (Dict[str, Tuple[float, float]]): Mapping from asset id to its (x, y) coordinates.

    Returns:
        go.Scatter: A Scatter trace with mode="lines"; x/y contain segment endpoints separated by
        None values so segments are independent, and hovertext contains the per-segment labels.
    """
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
        hover_text = f"{source_id} → {target_id}<br>Type: {rel_type}<br>Strength: {strength:.2f}"
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
    """
    Builds a Plotly Scatter trace containing markers and labels for the given asset IDs.

    Each marker's color is chosen from ASSET_CLASS_COLORS (falls back to "#7f7f7f" when the asset class key is missing). Marker size is 20 plus 5 per relationship for the asset, capped at an additional 30. Hover text shows the asset ID and its class. The ordering of points follows the order of `asset_ids` and positions are taken from `positions`.

    Parameters:
        graph (AssetRelationshipGraph): Graph containing asset objects and their relationship lists.
        positions (Dict[str, Tuple[float, float]]): Mapping from asset ID to (x, y) coordinates.
        asset_ids (List[str]): Asset IDs to include in the trace; their order determines point and label order.

    Returns:
        go.Scatter: A configured scatter trace with markers, text labels, and hover text for the assets.
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
