from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report_generator import SchemaReportGenerator


def generate_schema_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a Markdown report describing the schema and metrics for an AssetRelationshipGraph.
    
    Parameters:
        graph (AssetRelationshipGraph): The initialized asset graph to document.
    
    Returns:
        str: Markdown-formatted report describing the graph's schema, metrics, detected rules, and optimization recommendations.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()