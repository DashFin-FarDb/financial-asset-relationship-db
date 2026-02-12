from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a Markdown report describing the database schema,
    relationship distributions, calculated metrics,
    business/regulatory/valuation rules, and optimization recommendations
    for an asset relationship graph.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to analyze and summarize.

    Returns:
        markdown (str): A Markdown-formatted string containing the schema overview,
        relationship type distribution, network statistics and asset-class distributions,
        top relationships, business/regulatory/valuation rules, a computed data quality
        score with recommendation, and implementation notes.
    """
    metrics = graph.calculate_metrics()

    lines: list[str] = [
        "# Financial Asset Relationship Database Schema & Rules",
        "",
        "## Schema Overview",
        "",
        "### Entity Types",
        "1. **Equity** - Stock instruments with P/E ratio, dividend yield, EPS",
        "2. **Bond** - Fixed income with yield, coupon, maturity, credit rating",
        "3. **Commodity** - Physical assets with contracts and delivery dates",
        "4. **Currency** - FX pairs or single-currency proxies with exchange rates and policy links",
        "5. **Regulatory Events** - Corporate actions and SEC filings",
        "",
        "### Relationship Types",
    ]

    relationship_dist = metrics.get("relationship_distribution", {})
    for rel_type, count in sorted(
        relationship_dist.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        lines.append(f"- **{rel_type}**: {count} instances")

    lines.extend(
        [
            "",
            "## Calculated Metrics",
            "",
            "### Network Statistics",
            f"- **Total Assets**: {metrics.get('total_assets', 0)}",
            f"- **Total Relationships**: {metrics.get('total_relationships', 0)}",
            ("- **Average Relationship Strength**: " f"{metrics.get('average_relationship_strength', 0.0):.3f}"),
            f"- **Relationship Density**: {metrics.get('relationship_density', 0.0):.2f}%",
            f"- **Regulatory Events**: {metrics.get('regulatory_event_count', 0)}",
            "",
            "### Asset Class Distribution",
        ]
    )

    class_dist = metrics.get("asset_class_distribution", {})
    for asset_class, count in sorted(class_dist.items()):
        lines.append(f"- **{asset_class}**: {count} assets")

    lines.extend(["", "## Top Relationships"])

    top_relationships = metrics.get("top_relationships", [])
    for idx, (source, target, rel_type, strength) in enumerate(top_relationships, start=1):
        lines.append(f"{idx}. {source} → {target} ({rel_type}): {strength:.2%}")

    lines.extend(
        [
            "",
            "## Business Rules & Constraints",
            "",
            "### Cross-Asset Rules",
            ("1. **Corporate Bond Linkage**: Corporate bonds link to issuing company equity " "(directional)"),
            (
                "2. **Sector Affinity**: Assets in same sector have baseline relationship strength "
                "of 0.7 (bidirectional)"
            ),
            ("3. **Currency Exposure**: Non-USD assets link to their native currency asset when " "available"),
            ("4. **Income Linkage**: Equity dividends compared to bond yields using similarity " "score"),
            ("5. **Commodity Exposure**: Energy equities link to crude oil; miners link to metal " "commodities"),
            "",
            "### Regulatory Rules",
            "1. **Event Propagation**: Earnings events impact related bond and currency assets",
            "2. **Event Types**: SEC filings, earnings reports, dividend announcements",
            "3. **Impact Scoring**: Events range from -1 (negative) to +1 (positive)",
            ("4. **Related Assets**: Each event automatically creates relationships to impacted " "securities"),
            "",
            "### Valuation Rules",
            ("1. **Bond-Stock Spread**: Corporate bond yield - equity dividend yield indicates " "relative value"),
            ("2. **Sector Rotation**: Commodity prices trigger evaluation of sector exposure"),
            ("3. **Currency Adjustment**: All cross-border assets adjusted for FX exposure"),
            "",
            "## Schema Optimization Metrics",
            "",
            "### Data Quality Score:",
        ]
    )

    avg_strength = float(metrics.get("average_relationship_strength", 0.0))
    reg_events = float(metrics.get("regulatory_event_count", 0))
    quality_score = min(1.0, avg_strength + (reg_events / 10.0))
    lines.append(f"{quality_score:.1%}")
    lines.append("")
    lines.append("### Recommendation:")

    density = float(metrics.get("relationship_density", 0.0))
    if density > 30:
        lines.append("High connectivity - consider normalization")
    elif density > 10:
        lines.append("Well-balanced relationship graph - optimal for most use cases")
    else:
        lines.append("Sparse connections - consider adding more relationships")

    lines.extend(
        [
            "",
            "## Implementation Notes",
            "- All timestamps in ISO 8601 format",
            "- Relationship strengths normalized to 0-1 range",
            "- Impact scores on -1 to +1 scale for comparability",
            (
                "- Relationship directionality: some types are bidirectional "
                "(e.g., same_sector, income_comparison); others are directional"
            ),
        ]
    )

    return "\n".join(lines)
