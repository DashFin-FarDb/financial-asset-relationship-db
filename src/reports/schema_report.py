from __future__ import annotations

from typing import Any, Mapping

from src.logic.asset_graph import AssetRelationshipGraph


def _as_int(value: Any, default: int = 0) -> int:
    """Best-effort conversion to int (for count-like metrics)."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """Best-effort conversion to float (for ratio/score-like metrics)."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str_int_map(value: Any) -> dict[str, int]:
    """Return a dict[str, int] if possible, otherwise {}."""
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for k, v in value.items():
        if isinstance(k, str):
            out[k] = _as_int(v, 0)
    return out


def _as_top_relationships(value: Any) -> list[tuple[str, str, str, float]]:
    """
    Coerce the top_relationships list into a stable typed structure:
    list[(source, target, rel_type, strength)].
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
    Generate a Markdown report describing the database schema and
    relationship distributions, calculated metrics,
    business / regulatory / valuation rules, and optimization recommendations
    for an asset relationship graph.

    Args:
        graph: The asset relationship graph to analyze and summarize.

    Returns:
        A Markdown-formatted string containing the schema overview,
        relationship type distribution, network statistics, asset-class
        distributions, top relationships, business / regulatory / valuation
        rules, data quality score (from graph metrics), recommendations,
        and implementation notes.

    Raises:
        Exception: Propagates errors from graph.calculate_metrics().
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
        ("4. **Currency** - FX pairs or single-currency proxies with " "exchange rates and policy links"),
        "5. **Regulatory Events** - Corporate actions and SEC filings",
        "",
        "### Relationship Types",
    ]

    relationship_dist = _as_str_int_map(metrics.get("relationship_distribution"))
    for rel_type, count in sorted(
        relationship_dist.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        lines.append(f"- **{rel_type}**: {count} instances")

    total_assets = _as_int(metrics.get("total_assets"), 0)
    total_relationships = _as_int(metrics.get("total_relationships"), 0)
    avg_strength = _as_float(metrics.get("average_relationship_strength"), 0.0)
    density = _as_float(metrics.get("relationship_density"), 0.0)  # expected 0–100 (%)
    reg_events = _as_int(metrics.get("regulatory_event_count"), 0)
    quality_score = _as_float(metrics.get("quality_score"), 0.0)
    lines.extend(
        [
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

    lines.extend(["", "## Top Relationships"])
    top_relationships = _as_top_relationships(metrics.get("top_relationships"))

    for idx, (source, target, rel_type, strength) in enumerate(top_relationships, start=1):
        lines.append(f"{idx}. {source} → {target} ({rel_type}): {strength:.2%}")

    quality_score = _as_float(metrics.get("quality_score"), 0.0)

    quality_score = metrics.get("quality_score", 0.0)
    lines.append(f"Data Quality Score: {quality_score:.1%}")

    if density > 30.0:
        lines.append("High connectivity - consider normalization")
    elif density > 10.0:
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
