from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report_generator import SchemaReportGenerator


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a Markdown-formatted schema and metrics report for an AssetRelationshipGraph.
    
    Parameters:
        graph (AssetRelationshipGraph): The initialized asset relationship graph to analyze.
    
    Returns:
        str: Markdown-formatted report describing schema, metrics, rules, and optimization recommendations.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()