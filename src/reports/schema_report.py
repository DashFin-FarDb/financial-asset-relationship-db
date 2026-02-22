from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report_generator import SchemaReportGenerator


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a Markdown-formatted report describing an asset relationship graph's schema, metrics, rules, and optimization recommendations.
    
    Parameters:
        graph (AssetRelationshipGraph): The initialized asset relationship graph to analyze.
    
    Returns:
        str: Markdown-formatted report summarizing schema, metrics, rules, and recommendations.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()