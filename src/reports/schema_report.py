from __future__ import annotations

from typing import Any, Mapping

from src.logic.asset_graph import AssetRelationshipGraph


def _as_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to an integer, returning a fallback when conversion is
    not possible.

    Attempts to convert `value` to `int`. If `value` is `None` or cannot be
    converted, returns `default`.

    Parameters:
        value (Any): The input to convert to an integer.
        default (int): The value to return if conversion fails.

    Returns:
        int: The converted integer, or `default` if conversion is not possible.
    """
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """
    Coerce a value to a float, falling back to a default when conversion is not
    possible.

    Parameters:
        value (Any): Input to convert; if `None` or not convertible to float,
            the `default` is used.
        default (float): Value to return when `value` is `None` or cannot be
            converted.

    Returns:
        float: The converted float, or `default` if conversion fails.
    """
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str_int_map(value: Any) -> dict[str, int]:
    """
    Convert a mapping-like value into a dict[str, int], keeping only string keys.

    Parameters:
        value (Any): Input to coerce into a string-keyed mapping.

    Returns:
        dict[str, int]: A dictionary containing only items whose keys are strings;
            values are converted to integers (fallback to 0 for unconvertible values).
            Returns an empty dict if `value` is not a mapping.
    """
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for k, v in value.items():
        if isinstance(k, str):
            out[k] = _as_int(v, 0)
    return out


def _as_top_relationships(value: Any) -> list[tuple[str, str, str, float]]:
    """
    Normalize an input into a list of top relationship tuples
    (source, target, relationship type, strength).

    Parameters:
        value (Any): Input expected to be a list of 4-element tuples.
            Items that are not 4-tuples with string source, target, and
            relationship type are ignored.

     Returns:
         list[tuple[str, str, str, float]]: A list of validated tuples
             where the first three elements are strings
             and the fourth is a float strength
             (defaults to 0.0 when not convertible).
         Returns an empty list if the input is not a list or contains no
         valid items.
    """
    if not isinstance(value, list):
        return []

    out: list[tuple[str, str, str, float]] = []
    for item in value:
        if (
            isinstance(item, tuple)
            and len(item) == 4
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            and isinstance(item[2], str)
        ):
            out.append((item[0], item[1], item[2], _as_float(item[3], 0.0)))
    return out


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Produce a Markdown report summarizing schema, relationship
    distributions, calculated metrics, rules, and optimization
    recommendations for an asset relationship graph.

    Parameters:
        graph (AssetRelationshipGraph): The graph to analyze.

    Returns:
        A Markdown-formatted string containing:
        - Schema overview and entity/relationship types
        - Relationship type distribution and network statistics
        - Asset class distribution and top relationships
        - Business, regulatory, and valuation rules
        - Data quality score, density-based recommendations, and implementation notes
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
            "- **Sector Affinity**: Assets in the same sector are linked with strength 0.7 (bidirectional)",
            "- **Corporate Bond Linkage**: A bond whose issuer_id matches another asset creates a directional link (strength 0.9)",
            "- **Currency Exposure**: Currency assets reflect FX and central-bank policy links",
            "",
            "### Regulatory Rules",
            "- **Event Propagation**: Regulatory / earnings events propagate impact to related assets",
            "- Events create directional relationships from the event source to each related asset",
            "",
            "### Valuation Rules",
            "- **Impact Scoring**: Event impact scores are normalized to -1 to +1 for comparability",
            "- Relationship strengths are clamped to the 0-1 range",
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
