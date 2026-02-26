from __future__ import annotations

from typing import Any

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.helpers import (
    _as_float,
    _as_int,
    _as_str_int_map,
    _as_top_relationships,
)


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Produce a Markdown report that summarizes the schema,
    relationship distributions, calculated metrics, top relationships,
    business/regulatory/valuation rules, data quality score,
    recommendations, and implementation notes for an asset relationship
    graph.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to
            analyze and summarize.

    Returns:
        str: Markdown-formatted report containing the assembled schema
            overview, relationship type distribution, network statistics,
            asset-class distribution, top relationships, business and
            regulatory rules, data quality score, recommendations, and
            implementation notes.
    Raises:
        AttributeError: If ``graph`` is ``None`` or does not expose
            ``calculate_metrics``.
        Exception: Any exception raised by
            ``graph.calculate_metrics()`` propagates to the caller.
    """
    metrics: dict[str, Any] = graph.calculate_metrics()

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

    relationship_dist = _as_str_int_map(metrics.get("relationship_distribution"))
    for rel_type, count in sorted(
        relationship_dist.items(),
        key=lambda rel_tuple: rel_tuple[1],
        reverse=True,
    ):
        lines.append(f"- **{rel_type}**: {count} instances")

    total_assets = _as_int(metrics.get("total_assets"), 0)
    total_relationships = _as_int(metrics.get("total_relationships"), 0)
    avg_strength = _as_float(metrics.get("average_relationship_strength"), 0.0)
    density = _as_float(metrics.get("relationship_density"), 0.0)  # expected 0–100 (%)
    reg_events = _as_int(metrics.get("regulatory_event_count"), 0)
    lines.extend(
        [
            "",
            "",
            "## Calculated Metrics",
            "",
            "### Network Statistics",
            f"- **Total Assets**: {total_assets}",
            f"- **Total Relationships**: {total_relationships}",
            f"- **Average Relationship Strength**: {avg_strength:.3f}",
            f"- **Relationship Density**: {density:.2f}%",
            f"- **Regulatory Events**: {reg_events}",
            "",
            "### Asset Class Distribution",
        ]
    )

    class_dist = _as_str_int_map(metrics.get("asset_class_distribution"))
    for asset_class, count in sorted(class_dist.items()):
        lines.append(f"- **{asset_class}**: {count} assets")

    # -- Top Relationships ------------------------------------------------
    top_rels = _as_top_relationships(metrics.get("top_relationships"))
    lines.extend(["", "## Top Relationships", ""])
    if top_rels:
        for src, tgt, rtype, strength in top_rels:
            lines.append(f"- **{src}** -> **{tgt}** ({rtype}, strength {strength:.2f})")
    else:
        lines.append("- No relationships recorded yet.")

    # -- Business Rules & Constraints --------------------------------------
    lines.extend(
        [
            "",
            "## Business Rules & Constraints",
            "",
            "### Cross-Asset Rules",
            (
                "- **Sector Affinity**: Assets in the same sector are "
                "linked with strength 0.7 (bidirectional)"
            ),
            (
                "- **Corporate Bond Linkage**: A bond whose issuer_id matches another "
                "asset creates a directional link (strength 0.9)"
            ),
            (
                "- **Currency Exposure**: Currency assets reflect FX and "
                "central-bank policy links"
            ),
        ]
    )

    # -- Schema Optimization Metrics ---------------------------------------
    quality_score = _as_float(metrics.get("quality_score"), 0.0)
    lines.extend(
        [
            "",
            "## Schema Optimization Metrics",
            "",
            f"### Data Quality Score: {quality_score:.1%}",
            "",
            "### Recommendation:",
        ]
    )

    if density > 30.0:
        lines.append("High connectivity - consider normalization")
    elif density > 10.0:
        lines.append("Well-balanced relationship graph - optimal for most use cases")
    else:
        lines.append("Sparse connections - consider adding more relationships")

    # -- Implementation Notes ----------------------------------------------
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
