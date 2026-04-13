"""Schema report rendering helpers for asset relationship graphs."""

from __future__ import annotations

from datetime import datetime, timezone
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
    Coerce a mapping-like value into a dictionary with string keys and integer values.

    Parameters:
        value (Any): Input to coerce; if not a mapping, it will be treated as absent.

    Returns:
        dict[str, int]: A dictionary containing only entries whose keys are strings.
            Each value is converted to an integer with a fallback of 0.
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
    Normalize a value into a list of top-relationship tuples.

    Each returned tuple is (source, target, relationship_type, strength) where the first three elements are strings and `strength` is a float coerced from the input (defaults to 0.0 when not convertible).

    Parameters:
        value (Any): Expected to be a list of 4-element tuples; items that are not 4-tuples with string source, target, and relationship type are ignored.

    Returns:
        list[tuple[str, str, str, float]]: Validated top-relationship tuples. Returns an empty list if `value` is not a list or contains no valid items.
    """
    if not isinstance(value, list):
        return []

    out: list[tuple[str, str, str, float]] = []
    for item in value:
        if _is_valid_top_relationship_item(item):
            out.append((item[0], item[1], item[2], _as_float(item[3], 0.0)))
    return out


def _is_valid_top_relationship_item(item: Any) -> bool:
    """
    Validate that `item` represents a top-relationship entry.

    Parameters:
        item (Any): Value to check.

    Returns:
        bool: `True` if `item` is a 4-tuple whose first three elements are strings and the fourth element is present (strength), `False` otherwise.
    """
    if not isinstance(item, tuple):
        return False
    if len(item) != 4:
        return False
    return isinstance(item[0], str) and isinstance(item[1], str) and isinstance(item[2], str)


def _relationship_type_lines(metrics: Mapping[str, Any]) -> list[str]:
    """
    Generate markdown bullet lines describing relationship type counts sorted by descending count.

    Parameters:
        metrics (Mapping[str, Any]): Metrics mapping that may include a "relationship_distribution"
            mapping of relationship type to integer count.

    Returns:
        list[str]: Markdown-formatted lines (e.g., "- **{rel_type}**: {count} instances") sorted by count
        in descending order.
    """
    lines: list[str] = []
    relationship_dist = _as_str_int_map(metrics.get("relationship_distribution"))
    for rel_type, count in sorted(
        relationship_dist.items(),
        key=lambda rel_tuple: rel_tuple[1],
        reverse=True,
    ):
        lines.append(f"- **{rel_type}**: {count} instances")
    return lines


def _network_statistics_lines(
    metrics: Mapping[str, Any],
) -> tuple[list[str], float]:
    """
    Generate markdown lines for the network statistics section and return the parsed relationship density.

    Parameters:
        metrics (Mapping[str, Any]): Mapping containing numeric metrics. Expected keys:
            - "total_assets"
            - "total_relationships"
            - "average_relationship_strength"
            - "relationship_density"
            - "regulatory_event_count"
        Missing or invalid values are coerced to sensible defaults.

    Returns:
        tuple[list[str], float]: A tuple where the first element is a list of markdown lines for the
        "Calculated Metrics" / "Network Statistics" section (including an "Asset Class Distribution" header),
        and the second element is the relationship density parsed as a float.
    """
    total_assets = _as_int(metrics.get("total_assets"), 0)
    total_relationships = _as_int(metrics.get("total_relationships"), 0)
    avg_strength = _as_float(metrics.get("average_relationship_strength"), 0.0)
    density = _as_float(metrics.get("relationship_density"), 0.0)
    reg_events = _as_int(metrics.get("regulatory_event_count"), 0)
    lines = [
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
    return lines, density


def _asset_class_lines(metrics: Mapping[str, Any]) -> list[str]:
    """
    Generate markdown bullet lines describing the number of assets per asset class.

    Parameters:
        metrics (Mapping[str, Any]): Metrics mapping that may contain the key "asset_class_distribution" whose value is a mapping of asset class names to integer counts.

    Returns:
        list[str]: Markdown-formatted lines, each like "- **{asset_class}**: {count} assets".
    """
    lines: list[str] = []
    class_dist = _as_str_int_map(metrics.get("asset_class_distribution"))
    for asset_class, count in sorted(class_dist.items()):
        lines.append(f"- **{asset_class}**: {count} assets")
    return lines


def _top_relationship_lines(metrics: Mapping[str, Any]) -> list[str]:
    """
    Produce the markdown lines for the "Top Relationships" section using data from the metrics mapping.

    Parameters:
        metrics (Mapping[str, Any]): A metrics mapping that may include the "top_relationships" key; expected value is a list of relationship tuples.

    Returns:
        list[str]: Markdown lines for the section, including a header and either a list of formatted relationship entries or a placeholder stating no relationships are recorded.
    """
    lines = ["", "## Top Relationships", ""]
    top_rels = _as_top_relationships(metrics.get("top_relationships"))
    if top_rels:
        for src, tgt, rtype, strength in top_rels:
            lines.append(f"- **{src}** \u2192 **{tgt}** ({rtype}, strength {strength:.2f})")
    else:
        lines.append("- No relationships recorded yet.")
    return lines


def _density_recommendation_line(density: float) -> str:
    """
    Provide a short recommendation string based on network relationship density.

    Parameters:
        density (float): Relationship density expressed as a percentage (0 to 100).

    Returns:
        str: A recommendation message:
            - "High connectivity - consider normalization" when density > 30.0
            - "Well-balanced relationship graph - optimal for most use cases" when 10.0 < density <= 30.0
            - "Sparse connections - consider adding more relationships" when density <= 10.0
    """
    if density > 30.0:
        return "High connectivity - consider normalization"
    if density > 10.0:
        return "Well-balanced relationship graph - optimal for most use cases"
    return "Sparse connections - consider adding more relationships"


def _business_rules_lines() -> list[str]:
    """
    Provide static markdown lines describing business rules, constraints, and how events and relationships are modeled.

    Returns:
        list[str]: Ordered markdown lines for the "Business Rules & Constraints" section.
    """
    return [
        "",
        "## Business Rules & Constraints",
        "",
        "### Cross-Asset Rules",
        ("- **Sector Affinity**: Assets in the same sector are linked with strength 0.7 (bidirectional)"),
        (
            "- **Corporate Bond Linkage**: A bond whose issuer_id matches "
            "another asset creates a directional link (strength 0.9)"
        ),
        ("- **Currency Exposure**: Currency assets reflect FX and central-bank policy links"),
        "",
        "### Regulatory Rules",
        ("- **Event Propagation**: Regulatory / earnings events propagate impact to related assets"),
        ("- Events create directional relationships from the event source to each related asset"),
        "",
        "### Valuation Rules",
        ("- **Impact Scoring**: Event impact scores are normalized to -1 to +1 for comparability"),
        "- Relationship strengths are clamped to the 0-1 range",
    ]


def _schema_optimization_lines(
    metrics: Mapping[str, Any],
    density: float,
) -> list[str]:
    """
    Build the Schema Optimization section lines including the data quality score and a density-based recommendation.

    Parameters:
        metrics (Mapping[str, Any]): Mapping that may include 'quality_score' (a number between 0 and 1) used to format the Data Quality Score.
        density (float): Network relationship density as a percentage used to determine the recommendation text.

    Returns:
        section_lines (list[str]): Markdown-formatted lines for the Schema Optimization Metrics section.
    """
    quality_score = _as_float(metrics.get("quality_score"), 0.0)
    return [
        "",
        "## Schema Optimization Metrics",
        "",
        f"### Data Quality Score: {quality_score:.1%}",
        "",
        "### Recommendation:",
        _density_recommendation_line(density),
    ]


def _implementation_notes_lines() -> list[str]:
    """
    Provide static markdown lines for the "Implementation Notes" section describing formatting and normalization conventions (timestamp format, strength normalization, impact score range, and relationship directionality).

    Returns:
        lines (list[str]): A list of markdown strings forming the Implementation Notes section.
    """
    return [
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
        - Data quality score, density-based recommendations,
          and implementation notes
    """
    metrics: dict[str, Any] = graph.calculate_metrics()

    lines: list[str] = [
        "# Financial Asset Relationship Database Schema & Rules",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "## Schema Overview",
        "",
        "### Entity Types",
        ("1. **Equity** - Stock instruments with P/E ratio, dividend yield, EPS"),
        ("2. **Bond** - Fixed income with yield, coupon, maturity, credit rating"),
        "3. **Commodity** - Physical assets with contracts and delivery dates",
        ("4. **Currency** - FX pairs or single-currency proxies with exchange rates and policy links"),
        "5. **Regulatory Events** - Corporate actions and SEC filings",
        "",
        "### Relationship Types",
    ]

    lines.extend(_relationship_type_lines(metrics))

    stats_lines, density = _network_statistics_lines(metrics)
    lines.extend(stats_lines)
    lines.extend(_asset_class_lines(metrics))
    lines.extend(_top_relationship_lines(metrics))
    lines.extend(_business_rules_lines())
    lines.extend(_schema_optimization_lines(metrics, density))
    lines.extend(_implementation_notes_lines())

    return "\n".join(lines)
