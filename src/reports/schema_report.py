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

    lines.extend(["", "## Top Relationships", ""])

    top_relationships = metrics.get("top_relationships", [])
    for idx, (source, target, rel_type, strength) in enumerate(
        top_relationships, start=1
    ):
        lines.append(f"{idx}. {source} → {target} ({rel_type}): {strength:.2%}")

    lines.extend(
        [
            "",
            "## Business Rules & Constraints",
            "",
            "### Cross-Asset Rules",
            (
                "1. **Corporate Bond Linkage**: Corporate bonds link to issuing company equity "
                "(directional)"
            ),
            (
                "2. **Sector Affinity**: Assets in same sector have baseline relationship strength "
                "of 0.7 (bidirectional)"
            ),
            (
                "3. **Currency Exposure**: Non-USD assets link to their native currency asset when "
                "available"
            ),
            (
                "4. **Income Linkage**: Equity dividends compared to bond yields using similarity "
                "score"
            ),
            (
                "5. **Commodity Exposure**: Energy equities link to crude oil; miners link to metal "
                "commodities"
            ),
            "",
        ]
    )
    ("### Regulatory Rules",)
    (
        "1. **Event Propagation**: Earnings events impact related bond and currency assets",
    )
    ("2. **Event Types**: SEC filings, earnings reports, dividend announcements",)
    ("3. **Impact Scoring**: Events range from -1 (negative) to +1 (positive)",)
    (
        (
            "4. **Related Assets**: Each event automatically creates relationships to impacted "
            "securities"
        ),
    )
    avg_strength = metrics.get("average_relationship_strength", 0.0)
    reg_events = metrics.get("regulatory_event_count", 0)
    quality_score = min(1.0, avg_strength + (reg_events / 10.0))
    lines.append(f"{quality_score:.1%}")
    lines.append("")
    lines.append("### Recommendation:")

    density = metrics.get("relationship_density", 0.0)

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
