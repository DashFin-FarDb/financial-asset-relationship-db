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
    Create 2D line traces representing relationships between assets for visualization.

    Filters relationships between the given asset_ids using the provided boolean
    flags (unless show_all_relationships is True), ignores relationships where
    either asset lacks a position or is not in asset_ids, groups edges by
    relationship type, and returns one go.Scatter line trace per relationship
    type (colors taken from REL_TYPE_COLORS).

    Returns:
        List[go.Scatter]: A list of Scatter traces (one per relationship type)
        drawing lines between asset positions. Each trace includes hover text
        showing "source → target", relationship type, and strength; traces are
        named for legend display by relationship type.
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
    relationship_groups: Dict[str, list[dict[str, object]]] = {}

    for source_id in asset_ids:
        if source_id not in positions:
            continue
        rels = graph.relationships.get(source_id)
        if not rels:
            continue

        for target_id, rel_type, strength in rels:
            if target_id not in positions or target_id not in asset_id_set:
                continue

            if not show_all_relationships and rel_type in relationship_filters and not relationship_filters[rel_type]:
                continue

            relationship_groups.setdefault(rel_type, []).append(
                {"source_id": source_id, "target_id": target_id, "strength": strength}
            )

    traces: list[go.Scatter] = []
    for rel_type, relationships in relationship_groups.items():
        edges_x: list[float | None] = []
        edges_y: list[float | None] = []
        hover_texts: list[str | None] = []

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
                legendgroup=rel_type,
            )
        )

    return traces
