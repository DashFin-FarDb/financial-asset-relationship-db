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
    Format an iterable of lines into a single Markdown string.
    
    Returns:
        str: A single string composed of the input lines joined with newline characters.
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
        Initialize the SchemaReportGenerator.
        
        Parameters:
            graph (AssetRelationshipGraph): The graph whose metrics and structure will be used to build the report.
            formatter (Formatter | None): Optional callable that takes an iterable of report lines and returns the final formatted string.
                If omitted, a default formatter that joins lines with newline characters (Markdown-style) is used.
        """
        self.graph = graph
        self.formatter: Formatter = formatter or _default_formatter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> str:
        """
        Assembles all report sections and formats them into a single Markdown string.
        
        Returns:
            The complete formatted Markdown report as a string.
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
        Collect raw metrics for the current AssetRelationshipGraph.
        
        Returns:
            metrics (Metrics): Dictionary mapping metric names to their raw values (used by the report renderers).
        """
        return self.graph.calculate_metrics()

    # ------------------------------------------------------------------
    # Rendering sections
    # ------------------------------------------------------------------
    def _render_header(self) -> List[str]:
        """
        Builds the report's top-level Markdown header for the schema document.
        
        Returns:
            List[str]: Lines that form the header — a title line followed by a single blank line.
        """
        return [
            "# Financial Asset Relationship Database Schema & Rules",
            "",
        ]

    def _render_schema_overview(self) -> List[str]:
        """
        Render the "Schema Overview" section as a sequence of Markdown lines.
        
        Provides an "Entity Types" subsection listing example asset classes and brief attribute summaries.
        
        Returns:
            List[str]: Markdown-formatted lines constituting the Schema Overview section.
        """
        return [
            "## Schema Overview",
            "",
            "### Entity Types",
            "1. **Equity** – Stock instruments: P/E ratio, dividend yield, EPS",
            "2. **Bond** – Fixed income: yield, coupon, maturity, rating",
            "3. **Commodity** – Physical assets with delivery contracts",
            ("4. **Currency** – FX pairs or proxies with exchange-rate and " "monetary-policy links"),
            "5. **Regulatory Events** – Corporate actions and filings",
            "",
        ]

    def _render_relationship_types(self, metrics: Metrics) -> List[str]:
        """
        Render the "Relationship Types" Markdown section showing each relationship type and its instance count.
        
        Parameters:
            metrics (Metrics): Metric map expected to contain "relationship_distribution" — a mapping of relationship type names to integer counts.
        
        Returns:
            lines (List[str]): Markdown-formatted lines for the section, including a header, one bullet per relationship sorted by count (descending), and a trailing blank line.
        """
        dist = _as_str_int_map(metrics.get("relationship_distribution"))
        lines = ["### Relationship Types"]
        for rel, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{rel}**: {count} instances")
        lines.append("")
        return lines

    def _render_calculated_metrics(self, metrics: Metrics) -> List[str]:
        """
        Render the "Calculated Metrics" Markdown section summarizing network statistics.
        
        Parameters:
            metrics (Metrics): Mapping of metric names to values produced by the graph. Expected keys:
                - "total_assets": total number of assets
                - "total_relationships": total number of relationships
                - "average_relationship_strength": mean strength of relationships
                - "relationship_density": network density as a percentage
                - "regulatory_event_count": count of regulatory events
        
        Returns:
            List[str]: Lines of Markdown comprising a "Calculated Metrics" section with a
            "Network Statistics" subsection. Includes lines for total assets, total
            relationships, average relationship strength (formatted to three decimal
            places), relationship density (formatted to two decimal places with a
            percent sign), and regulatory events.
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
            metrics (Metrics): Metrics dictionary expected to contain an "asset_class_distribution"
                mapping of asset class names to integer counts.
        
        Returns:
            List[str]: Lines of Markdown for the section; one header, one bullet per asset class
            formatted as "- **<class>**: <count> assets", and a trailing blank line.
        """
        dist = _as_str_int_map(metrics.get("asset_class_distribution"))
        lines = ["### Asset Class Distribution"]
        for cls, count in sorted(dist.items()):
            lines.append(f"- **{cls}**: {count} assets")
        lines.append("")
        return lines

    def _render_top_relationships(self, metrics: Metrics) -> List[str]:
        """
        Render the "Top Relationships" Markdown section as a list of lines.
        
        The function reads top relationship entries from metrics["top_relationships"] (if present) and produces a Markdown section header and one list item per relationship in the form:
        "- **src** → **tgt** (rtype, strength X.XX)". If no top relationships are available, the section will contain a single bullet stating that no relationships are recorded.
        
        Parameters:
            metrics (Metrics): Dictionary of collected metrics; expected to contain an optional "top_relationships" entry.
        
        Returns:
            lines (List[str]): Ordered list of Markdown lines composing the "Top Relationships" section, including header and trailing blank line.
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
        Return the Markdown lines for the "Business Rules & Constraints" section of the report.
        
        This fixed section lists domain rules used when interpreting the asset relationship graph and includes three subsections: Cross-Asset Rules, Regulatory Rules, and Valuation Rules.
        
        Returns:
            lines (List[str]): Markdown-formatted lines for the business rules section.
        """
        return [
            "## Business Rules & Constraints",
            "",
            "### Cross-Asset Rules",
            "- **Sector Affinity**: Same-sector assets link at strength 0.7.",
            ("- **Corporate Bond Linkage**: issuer_id match creates a " "directional link (strength 0.9)."),
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
        Builds the "Schema Optimization Metrics" Markdown section for the report.
        
        Parameters:
            metrics (Metrics): Metrics dictionary; uses `relationship_density` and `quality_score` to produce the section.
        
        Returns:
            List[str]: Markdown lines for the "Schema Optimization Metrics" section, including a formatted Data Quality Score and a density-based recommendation.
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
        Return the Markdown lines for the "Implementation Notes" section of the report.
        
        Returns:
            lines (List[str]): Ordered list of Markdown-formatted lines describing timestamp format, normalization ranges for strengths and impact scores, and relationship directionality.
        """
        return [
            "## Implementation Notes",
            "- ISO-8601 timestamps.",
            "- Strengths normalized to 0–1.",
            "- Impact scores normalized to −1 to +1.",
            ("- Directionality varies by relationship type: " "some are bidirectional, others directional."),
            "",
        ]