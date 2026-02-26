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
    """
    Join an iterable of lines into a single Markdown-formatted string.

    Parameters:
        lines (Iterable[str]): Iterable of lines or paragraphs to join; each item becomes a separate line.

    Returns:
        str: The concatenated string with newline separators.
    """
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
        """
        Initialize the SchemaReportGenerator with the graph to report on and an optional formatter.

        Parameters:
            graph (AssetRelationshipGraph): Source AssetRelationshipGraph whose metrics and relationships will be used to build the report.
            formatter (Formatter | None): Callable that takes an iterable of report lines and returns the final string. If None, a default formatter that joins lines with newlines is used.
        """
        self.graph = graph
        self.formatter: Formatter = formatter or _default_formatter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> str:
        """
        Generate the complete Markdown report for the associated AssetRelationshipGraph.

        Collects metrics from the graph, renders each report section in the defined order, aggregates the section lines, and applies the configured formatter.

        Returns:
            str: The assembled report as a Markdown-formatted string.
        """
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
        """
        Retrieve calculated metrics from the associated AssetRelationshipGraph.

        Returns:
            metrics (Metrics): A dictionary mapping metric names to their values.
        """
        return self.graph.calculate_metrics()

    # ------------------------------------------------------------------
    # Rendering sections
    # ------------------------------------------------------------------
    def _render_header(self) -> List[str]:
        """
        Return the top-level report header lines for the schema document.

        Returns:
            lines (List[str]): Two-element list containing the Markdown title and a blank separator line.
        """
        return [
            "# Financial Asset Relationship Database Schema & Rules",
            "",
        ]

    def _render_schema_overview(self) -> List[str]:
        """
        Render the "Schema Overview" section lines for the report.

        Returns:
            lines (List[str]): Markdown lines for the "Schema Overview" section, including an "Entity Types" subsection with brief descriptors for Equity, Bond, Commodity, Currency, and Regulatory Events.
        """
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
        """
        Render the "Relationship Types" Markdown subsection listing each relationship type and its instance count.

        Parameters:
            metrics (Metrics): Metrics dictionary expected to contain a "relationship_distribution" mapping of relationship type names to counts.

        Returns:
            List[str]: Lines of Markdown for the "Relationship Types" section, ordered by descending instance count and terminated with a blank line.
        """
        dist = _as_str_int_map(metrics.get("relationship_distribution"))
        lines = ["### Relationship Types"]
        for rel, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{rel}**: {count} instances")
        lines.append("")
        return lines

    def _render_calculated_metrics(self, metrics: Metrics) -> List[str]:
        """
        Assembles the "Calculated Metrics" Markdown section describing core network statistics.

        Parameters:
            metrics (Metrics): Mapping of metric names to values. Recognized keys:
                - "total_assets": total number of assets (int-able)
                - "total_relationships": total number of relationships (int-able)
                - "average_relationship_strength": average strength (float-able)
                - "relationship_density": density as percentage (float-able)
                - "regulatory_event_count": count of regulatory events (int-able)

        Returns:
            List[str]: Lines of Markdown for the "Calculated Metrics" -> "Network Statistics" subsection,
            with formatted values for total assets, total relationships, average relationship strength
            (three decimal places), relationship density (two decimal places with percent sign), and
            regulatory events.
        """
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
        """
        Render the "Asset Class Distribution" section as Markdown lines.

        Parameters:
            metrics (Metrics): Metrics dictionary containing an "asset_class_distribution" mapping of asset class names to counts.

        Returns:
            List[str]: Lines for the section including the header, one bullet per asset class formatted as "**Class**: N assets", and a trailing blank line.
        """
        dist = _as_str_int_map(metrics.get("asset_class_distribution"))
        lines = ["### Asset Class Distribution"]
        for cls, count in sorted(dist.items()):
            lines.append(f"- **{cls}**: {count} assets")
        lines.append("")
        return lines

    def _render_top_relationships(self, metrics: Metrics) -> List[str]:
        """
        Render the "Top Relationships" report section as a list of Markdown lines.

        Parameters:
            metrics (Metrics): Metrics mapping that may include a "top_relationships" entry; each top relationship is expected as an iterable of (source, target, relationship_type, strength).

        Returns:
            List[str]: Markdown-formatted lines for the "Top Relationships" section. If no top relationships are present, the list contains a single bullet stating that no relationships are recorded. Each relationship line appears as:
            "- **<source>** → **<target>** (<relationship_type>, strength <strength formatted to two decimals>)"
        """
        top = _as_top_relationships(metrics.get("top_relationships"))
        lines = ["## Top Relationships", ""]
        if not top:
            return lines + ["- No relationships recorded yet.", ""]

        for src, tgt, rtype, strength in top:
            lines.append(f"- **{src}** → **{tgt}** ({rtype}, strength {strength:.2f})")
        lines.append("")
        return lines

    def _render_business_rules(self) -> List[str]:
        """
        Render the "Business Rules & Constraints" report section as a list of Markdown lines.

        The returned lines form the "Business Rules & Constraints" section and include subsections for Cross-Asset Rules, Regulatory Rules, and Valuation Rules with concise rule descriptions.

        Returns:
            List[str]: Markdown-formatted lines for the section.
        """
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
            ("- Event nodes create directional edges to affected assets."),
            "",
            "### Valuation Rules",
            "- **Impact Scoring**: Normalized to −1 to +1.",
            "- **Strength Normalization**: Relationship strengths clamped to 0–1.",
            "",
        ]

    def _render_schema_optimization(self, metrics: Metrics) -> List[str]:
        """
        Render the "Schema Optimization Metrics" section as Markdown lines.

        Parameters:
            metrics (Metrics): Dictionary of metric values. Expected keys:
                - "relationship_density": numeric value or coercible type used to select a recommendation.
                - "quality_score": numeric value or coercible type used to display a data quality percentage.

        Returns:
            List[str]: Lines of Markdown composing the Schema Optimization Metrics section, including a formatted
            Data Quality Score and a recommendation determined by relationship density.
        """
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
        """
        Produce the "Implementation Notes" section as a list of Markdown-formatted lines.

        Returns:
            List[str]: Lines that form the "Implementation Notes" section, including timestamp format, normalization conventions for strengths and impact scores, directionality note, and a trailing blank line.
        """
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
