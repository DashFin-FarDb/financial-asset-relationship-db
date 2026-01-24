from src.logic.asset_graph import AssetRelationshipGraph


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a human-readable Markdown report describing the
    asset relationship schema, calculated network metrics,
    top relationships, business/regulatory/valuation rules,
    and optimization recommendations.

    The report is assembled from metrics computed by the provided
    AssetRelationshipGraph and includes:
    - schema overview (entity and relationship types),
    - relationship distribution and asset class breakdown,
    - network statistics (total assets/relationships, average strength,
      density, regulatory events),
    - ordered top relationships with strengths,
    - predefined business, regulatory, and valuation rules,
    - a data quality score and a textual recommendation
      based on relationship density,
    - implementation notes.

    Parameters:
        graph (AssetRelationshipGraph): Graph instance used to calculate
          metrics required for the report.

    Returns:
        str: Complete Markdown-formatted report summarizing
            schema, metrics, rules, and recommendations.
    """

    schema_report = """# Financial Asset Relationship Database Schema & Rules
"""
    schema_report += """
# Schema Overview


# Entity Types
1. ** Equity ** - Stock instruments with P / E ratio, dividend yield , EPS
2. ** Bond ** - Fixed income with yield , coupon, maturity, credit rating
3. ** Commodity ** - Physical assets with contracts and delivery dates
4. ** Currency ** - FX pairs or single - currency proxies with exchange rates and policy links
5. ** Regulatory Events ** - Corporate actions and SEC filings

# Relationship Types
    for rel_type, count in sorted(
        metrics["relationship_distribution"].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        report += f"- **{rel_type}**: {count} instances\n"
    report += f"""


# Calculated Metrics
```markdown
# Network Statistics
- **Total Assets**: {metrics["total_assets"]}
- **Total Relationships**: {metrics["total_relationships"]}
"""
    report += (
        f"- **Average Relationship Strength**: "
        f"{metrics['average_relationship_strength']:.3f}\n"
    )
    report += (
        f"- **Relationship Density**: "
        f"{metrics['relationship_density']:.2f}%\n"
    )
    report += f"- **Regulatory Events**: {metrics['regulatory_event_count']}\n\n"

    # Asset Class Distribution
    asset_count = None
    for asset_class, count in sorted(metrics["asset_class_distribution"].items()):
        asset_count = count
        report += f"- **{asset_class}**: {asset_count} assets\n"

    report += "\n# Top Relationships\n"
    relationship_type = None
    for idx, (source, target, rel_type, strength) in enumerate(metrics["top_relationships"], 1):
        relationship_type = rel_type
        report += f"{idx}. {source} → {target} ({relationship_type}): {strength:.2%}\n"

    report += "\n# Business Rules & Constraints\n\n# Cross-Asset Rules\n"
    report += (
        "1. **Corporate Bond Linkage**: Corporate bonds link to issuing "
        "company equity (directional)\n"
        "2. **Sector Affinity**: Assets in same sector have baseline "
        "relationship\n"
        "3. **Correlation Strength**: Asset pairs have minimum strength "
        "of 0.7 (bidirectional)\n"
        "4. **Currency Exposure**: Non-USD assets link to their native "
        "currency asset when available\n"
        "5. **Income Linkage**: Equity dividends compared to bond yields "
        "using similarity score\n"
        "6. **Commodity Exposure**: Energy equities link to crude oil; "
        "miners link to metal commodities\n"
    )

    report += "\n# Regulatory Rules\n"
    report += (
        "1. **Event Propagation**: Earnings events impact related bond "
        "and currency assets\n"
        "2. **Impact Scoring**: Events range from -1 (negative) to +1 "
        "(positive)\n"
        "3. **Related Assets**: Each event automatically creates "
        "relationships to impacted securities\n"
    )

    report += (
        "\n# Valuation Rules\n"
        "1. **Bond-Stock Spread**: Corporate bond yield - equity dividend "
        "yield indicates relative value\n"
        "2. **Sector Rotation**: Commodity prices trigger evaluation "
def generate_schema_report(metrics):
    report += (
        "of sector exposure\n"
        "3. **Currency Adjustment**: All cross-border assets adjusted "
        "for FX exposure\n"
    )

    report += """
# Schema Optimization Metrics

# Data Quality Score: """
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
    return report
