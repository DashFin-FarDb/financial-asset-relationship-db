from src.logic.asset_graph import AssetRelationshipGraph


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """Generate schema and rules report"""
    metrics = graph.calculate_metrics()

    report = (
        "# Financial Asset Relationship Database Schema & Rules\n\n"
        "## Schema Overview\n\n"
        "### Entity Types\n"
        "1. **Equity** - Stock instruments with P/E ratio, dividend yield, EPS\n"
        "2. **Bond** - Fixed income with yield, coupon, maturity, credit rating\n"
        "3. **Commodity** - Physical assets with contracts and delivery dates\n"
        "4. **Currency** - FX pairs or single-currency proxies with exchange rates "
        "and policy links\n"
        "5. **Regulatory Events** - Corporate actions and SEC filings\n\n"
        "### Relationship Types\n"
    )

    for rel_type, count in sorted(
        metrics["relationship_distribution"].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        report += f"- **{rel_type}**: {count} instances\n"

    report += (
        "\n## Calculated Metrics\n\n"
        "### Network Statistics\n"
        f"- **Total Assets**: {metrics['total_assets']}\n"
        f"- **Total Relationships**: {metrics['total_relationships']}\n"
        "- **Average Relationship Strength**: "
        f"{metrics['average_relationship_strength']:.3f}\n"
        "- **Relationship Density**: "
        f"{metrics['relationship_density']:.2f}%\n"
        "- **Regulatory Events**: "
        f"{metrics['regulatory_event_count']}\n\n"
        "### Asset Class Distribution\n"
    )

    for asset_class, count in sorted(metrics["asset_class_distribution"].items()):
        report += f"- **{asset_class}**: {count} assets\n"

    report += (
        "\n## Top Relationships\n"
    )

for idx, (source, target, rel_type, strength) in enumerate(
    metrics["top_relationships"], 1
):
    report += f"{idx}. {source} → {target} ({rel_type}): {strength:.2%}\n"

report += (
    "\n## Business Rules & Constraints\n\n"
    "### Cross-Asset Rules\n"
)
report += (
    "1. **Corporate Bond Linkage**: Corporate bonds link to"
    " issuing company equity (directional)\n"
    "2. **Sector Affinity**: Assets in same sector have baseline"
    " relationship strength of 0.7 (bidirectional)\n"
    "3. **Currency Exposure**: Non-USD assets link to their native"
    " currency asset when available\n"
    "4. **Income Linkage**: Equity dividends compared to bond yields"
    " using similarity score\n"
    "5. **Commodity Exposure**: Energy equities link to crude oil; miners"
    " link to metal commodities\n"
)
report += (
    "\n### Regulatory Rules\n"
)
report += (
    "1. **Event Propagation**: Earnings events impact related bond and\n"
    "currency assets\n"
)
report += (
    "2. **Event Types**: SEC filings, earnings reports, dividend "
    "announcements\n"
    "3. **Impact Scoring**: Events range from -1 (negative) "
    "to +1 (positive)\n"
    "4. **Related Assets**: Each event automatically "
    "creates relationships to impacted securities\n"
)
report += """

### Valuation Rules
"""
report += (
    "1. **Bond-Stock Spread**: Corporate bond yield - equity dividend yield "
    "indicates relative value\n"
    "2. **Sector Rotation**: Commodity prices trigger "
    "evaluation of sector exposure\n"
    "3. **Currency Adjustment**: All cross-border assets "
    "adjusted for FX exposure\n"
)
report += """

## Schema Optimization Metrics

### Data Quality Score: """

quality_score = min(
    1.0,
    metrics["average_relationship_strength"] + (metrics["regulatory_event_count"] / 10),
)
report += f"{quality_score:.1%}\n"
report += "\n### Recommendation: "
if metrics["relationship_density"] > 30:
    report += "High connectivity - consider normalization"
elif metrics["relationship_density"] > 10:
    report += "Well-balanced relationship graph - optimal for most use cases"
else:
    report += "Sparse connections - consider adding more relationships"

report += "\n\n## Implementation Notes\n- All timestamps in ISO 8601 format\n"
report += "- Relationship strengths normalized to 0-1 range\n"
report += "- Impact scores on -1 to +1 scale for comparability\n"
report += (
    "- Relationship directionality: some types are bidirectional (e.g.,\n"
    "  same_sector, income_comparison);\n"
    "  others are directional\n"
)
return report
