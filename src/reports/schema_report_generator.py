from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Tuple

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.helpers import (
    _as_float,
    _as_int,
    _as_str_int_map,
    _as_top_relationships,
)


Formatter = Callable[[Iterable[str]], str]
Metrics = Dict[str, Any]


def _default_formatter(lines: Iterable[str]) -> str:
    """Join lines into a Markdown string."""
    return "\n".join(lines)


class SchemaReportGenerator:
    """
    Generate a structured Markdown schema + metrics report for an
    AssetRelationshipGraph.

    This class provides a modular architecture where each logical
    section of the report is rendered independently to support
    granular testing and override-based extensions.
    """

    def __init__(
        self,
        graph: AssetRelationshipGraph,
        formatter: Formatter | None = None,
    ) -> None:
        self.graph = graph
        self.formatter: Formatter = formatter or _default_formatter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> str:
        """Produce the full Markdown report."""
        metrics = self._collect_metrics()

        sections: List[str] = []
        sections.extend(self._render_header())
        sections.extend(self._render_schema_overview())
        sections.extend(self._render_relationship_types(metrics))
        sections.extend(self._render_calculated_metrics(metrics))
        sections.extend(self._render_asset_class_distribution(metrics))
        sections.extend(self._render_top_relationships(metrics))
        sections.extend(self._render_business_rules())
        sections.extend(self._render_schema_optimization(metrics))
        sections.extend(self._render_implementation_notes())

        return self.formatter(sections)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _collect_metrics(self) -> Metrics:
        """Fetch raw metrics from the graph and return as a dict."""
        return self.graph.calculate_metrics()

    # ------------------------------------------------------------------
    # Rendering sections
    # ------------------------------------------------------------------
    def _render_header(self) -> List[str]:
        return [
            "# Financial Asset Relationship Database Schema & Rules",
            "",
        ]

    def _render_schema_overview(self) -> List[str]:
        return [
            "## Schema Overview",
            "",
            "### Entity Types",
            "1. **Equity** – Stock instruments: P/E ratio, dividend yield, EPS",
            "2. **Bond** – Fixed income: yield, coupon, maturity, rating",
            "3. **Commodity** – Physical assets with delivery contracts",
            (
                "4. **Currency** – FX pairs or proxies with exchange-rate and "
                "monetary-policy links"
            ),
            "5. **Regulatory Events** – Corporate actions and filings",
            "",
        ]

    def _render_relationship_types(self, metrics: Metrics) -> List[str]:
        dist = _as_str_int_map(metrics.get("relationship_distribution"))
        lines = ["### Relationship Types"]
        for rel, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{rel}**: {count} instances")
        lines.append("")
        return lines

    def _render_calculated_metrics(self, metrics: Metrics) -> List[str]:
        total_assets = _as_int(metrics.get("total_assets"))
        total_rels = _as_int(metrics.get("total_relationships"))
        avg_strength = _as_float(metrics.get("average_relationship_strength"))
        density = _as_float(metrics.get("relationship_density"))
        reg_events = _as_int(metrics.get("regulatory_event_count"))

        return [
            "## Calculated Metrics",
            "",
            "### Network Statistics",
            f"- **Total Assets**: {total_assets}",
            f"- **Total Relationships**: {total_rels}",
            f"- **Average Relationship Strength**: {avg_strength:.3f}",
            f"- **Relationship Density**: {density:.2f}%",
            f"- **Regulatory Events**: {reg_events}",
            "",
        ]

    def _render_asset_class_distribution(self, metrics: Metrics) -> List[str]:
        dist = _as_str_int_map(metrics.get("asset_class_distribution"))
        lines = ["### Asset Class Distribution"]
        for cls, count in sorted(dist.items()):
            lines.append(f"- **{cls}**: {count} assets")
        lines.append("")
        return lines

    def _render_top_relationships(self, metrics: Metrics) -> List[str]:
        top = _as_top_relationships(metrics.get("top_relationships"))
        lines = ["## Top Relationships", ""]
        if not top:
            return lines + ["- No relationships recorded yet.", ""]

        for src, tgt, rtype, strength in top:
            lines.append(
                f"- **{src}** → **{tgt}** ({rtype}, strength {strength:.2f})"
            )
        lines.append("")
        return lines

    def _render_business_rules(self) -> List[str]:
        return [
            "## Business Rules & Constraints",
            "",
            "### Cross-Asset Rules",
            "- **Sector Affinity**: Same-sector assets link at strength 0.7.",
            (
                "- **Corporate Bond Linkage**: issuer_id match creates a "
                "directional link (strength 0.9)."
            ),
            "- **Currency Exposure**: FX and central-bank policy effects included.",
            "",
            "### Regulatory Rules",
            "- **Event Propagation**: Regulatory/earnings events propagate impact.",
            (
                "- Event nodes create directional edges to affected assets."
            ),
            "",
            "### Valuation Rules",
            "- **Impact Scoring**: Normalized to −1 to +1.",
            "- **Strength Normalization**: Relationship strengths clamped to 0–1.",
            "",
        ]

    def _render_schema_optimization(self, metrics: Metrics) -> List[str]:
        density = _as_float(metrics.get("relationship_density"))
        quality_score = _as_float(metrics.get("quality_score"))

        lines = [
            "## Schema Optimization Metrics",
            "",
            f"### Data Quality Score: {quality_score:.1%}",
            "",
            "### Recommendation:",
        ]

        if density > 30.0:
            lines.append("High connectivity – consider normalization.")
        elif density > 10.0:
            lines.append("Well-balanced – suitable for most analytical use-cases.")
        else:
            lines.append("Sparse – consider enriching relationship definitions.")

        lines.append("")
        return lines

    def _render_implementation_notes(self) -> List[str]:
        return [
            "## Implementation Notes",
            "- ISO-8601 timestamps.",
            "- Strengths normalized to 0–1.",
            "- Impact scores normalized to −1 to +1.",
            (
                "- Directionality varies by relationship type: "
                "some are bidirectional, others directional."
            ),
            "",
        ]
