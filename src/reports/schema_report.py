from src.logic.asset_graph import AssetRelationshipGraph


def generate_schema_report(_graph: AssetRelationshipGraph) -> str:
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
        _graph (AssetRelationshipGraph): Graph instance used to calculate
          metrics required for the report.

    Returns:
        str: Complete Markdown-formatted report summarizing
            schema, metrics, rules, and recommendations.
    """

    metrics = _graph.compute_metrics()
    report = ""

    report += "\n# Network Statistics\n"
    report += f"- **Total Assets**: {metrics['total_assets']}\n"
    report += f"- **Total Relationships**: {metrics['total_relationships']}\n"

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
        "of sector exposure\n"
        "3. **Currency Adjustment**: All cross-border assets adjusted "
        "for FX exposure\n"
    )

    return report


def generate_schema_optimization_report(metrics):
    """Generate a schema optimization report based on provided metrics.

    Computes a data quality score based on relationship strength and
    regulatory event count, provides recommendations based on relationship
    density, and appends implementation notes.
    """
    report_content = ""
    report_content += """
# Schema Optimization Metrics

# Data Quality Score: """
    quality_score = min(
        1.0,
        metrics["average_relationship_strength"]
        + (metrics["regulatory_event_count"] / 10),
    )
    report_content += f"{quality_score:.1%}\n"

    report_content += "\n### Recommendation: "
    if metrics["relationship_density"] > 30:
        report_content += "High connectivity - consider normalization"
    elif metrics["relationship_density"] > 10:
        report_content += (
            "Well-balanced relationship graph - optimal for most use cases"
        )
    else:
        report_content += "Sparse connections - consider adding more relationships"

    report_content += (
        "\n\n## Implementation Notes\n- All timestamps in ISO 8601 format\n"
    )
    report_content += "- Relationship strengths normalized to 0-1 range\n"
    return report_content
