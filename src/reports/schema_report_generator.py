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
    
    Parameters:
        lines (Iterable[str]): Lines or fragments that will be concatenated.
    
    Returns:
        str: The lines joined with a single newline character between each.
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
        Initialize the SchemaReportGenerator with the source graph and an optional output formatter.
        
        Parameters:
            graph (AssetRelationshipGraph): The asset relationship graph used to collect metrics and render the report.
            formatter (Formatter | None): Optional callable that takes an iterable of lines and returns the formatted report string.
                If omitted, the module-level _default_formatter is used.
        """
        self.graph = graph
        self.formatter: Formatter = formatter or _default_formatter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> str:
        """
        Builds the complete Markdown report for the generator's graph.
        
        Assembles the report sections, applies the configured formatter, and returns the final Markdown document.
        
        Returns:
            markdown (str): The composed Markdown report as a single string.
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
        Collect metrics from the underlying AssetRelationshipGraph for report generation.
        
        Returns:
            metrics (Metrics): Dictionary of raw metrics produced by the graph's `calculate_metrics`.
        """
        return self.graph.calculate_metrics()

    # ------------------------------------------------------------------
    # Rendering sections
    # ------------------------------------------------------------------
    def _render_header(self) -> List[str]:
        """
        Return the top-level Markdown header for the report as a list of lines.
        
        Returns:
            List[str]: Lines comprising the main report title and a trailing blank line.
        """
        return [
            "# Financial Asset Relationship Database Schema & Rules",
            "",
        ]

    def _render_schema_overview(self) -> List[str]:
        """
        Create the "Schema Overview" Markdown section as a sequence of lines.
        
        Returns:
            lines (List[str]): Ordered lines that form the "Schema Overview" section, including the header, an "Entity Types" subsection, and a numbered list of entity type descriptions (Equity, Bond, Commodity, Currency, Regulatory Events).
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
        Builds the "Relationship Types" Markdown section listing relationship types sorted by count descending.
        
        Parameters:
            metrics (Metrics): Metrics dictionary containing a "relationship_distribution" mapping of relationship name to integer count.
        
        Returns:
            List[str]: Lines of Markdown for the section; includes a header, one bullet per relationship in the form "`- **<rel>**: <count> instances`", and a trailing blank line.
        """
        dist = _as_str_int_map(metrics.get("relationship_distribution"))
        lines = ["### Relationship Types"]
        for rel, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{rel}**: {count} instances")
        lines.append("")
        return lines

    def _render_calculated_metrics(self, metrics: Metrics) -> List[str]:
        """
        Builds the "Calculated Metrics" Markdown section as a list of lines containing network statistics.
        
        Parameters:
            metrics (Metrics): Mapping containing metric values used to render the section. Expected keys include
                "total_assets", "total_relationships", "average_relationship_strength",
                "relationship_density", and "regulatory_event_count".
        
        Returns:
            List[str]: Lines of Markdown for the "Calculated Metrics" section. The list includes a section header,
            a "Network Statistics" subsection, and formatted metric lines where average relationship strength is
            formatted to three decimal places and relationship density is shown as a percentage with two decimals.
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
        Render the "Asset Class Distribution" Markdown section as a list of lines.
        
        Parameters:
            metrics (Metrics): Metrics dictionary expected to contain the key "asset_class_distribution"
                with a mapping of asset class names to integer counts.
        
        Returns:
            List[str]: Markdown lines for the section, one line per asset class sorted by class name,
            followed by a trailing blank line.
        """
        dist = _as_str_int_map(metrics.get("asset_class_distribution"))
        lines = ["### Asset Class Distribution"]
        for cls, count in sorted(dist.items()):
            lines.append(f"- **{cls}**: {count} assets")
        lines.append("")
        return lines

    def _render_top_relationships(self, metrics: Metrics) -> List[str]:
        """
        Render the "Top Relationships" section as Markdown lines for the report.
        
        Parameters:
            metrics (Metrics): Metrics dictionary; expects the key "top_relationships" containing an iterable of
                tuples (source, target, relationship_type, strength).
        
        Returns:
            List[str]: A list of Markdown lines representing the "Top Relationships" section. If no top relationships
            are present, the list includes a single bullet indicating none are recorded.
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
        Render the "Business Rules & Constraints" section as Markdown lines.
        
        This section includes subheadings for Cross-Asset Rules, Regulatory Rules, and Valuation Rules and provides bullet-pointed business constraints and normalization rules.
        
        Returns:
            lines (List[str]): Markdown-formatted lines comprising the "Business Rules & Constraints" section.
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
        Builds the "Schema Optimization Metrics" section as Markdown lines.
        
        Parameters:
            metrics (Metrics): Mapping that should include:
                - "relationship_density": numeric value (percentage-like) used to decide recommendations.
                - "quality_score": numeric value between 0 and 1 representing data quality.
        
        Returns:
            List[str]: Markdown lines for the "Schema Optimization Metrics" section, including a formatted data quality score and a density-based recommendation.
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
        Render the Implementation Notes section as a list of Markdown lines.
        
        Returns:
            lines (List[str]): Markdown-formatted lines for the "Implementation Notes" section,
            including notes on timestamps, normalization ranges, directionality, and a trailing blank line.
        """
        return [
            "## Implementation Notes",
            "- ISO-8601 timestamps.",
            "- Strengths normalized to 0–1.",
            "- Impact scores normalized to −1 to +1.",
            ("- Directionality varies by relationship type: " "some are bidirectional, others directional."),
            "",
        ]