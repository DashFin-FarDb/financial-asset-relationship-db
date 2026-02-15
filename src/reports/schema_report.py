from __future__ import annotations

from typing import Any

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report_generator import SchemaReportGenerator


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Produce a Markdown-formatted schema + metrics report for an
    AssetRelationshipGraph.

    This is a thin wrapper that instantiates SchemaReportGenerator and
    delegates full report construction to it. This maintains a stable
    function-level API while allowing the underlying report generation
    system to evolve independently.

    Parameters:
        graph (AssetRelationshipGraph): The initialized asset graph.

    Returns:
        str: Markdown report describing schema, metrics, rules, and
            optimization recommendations.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()
