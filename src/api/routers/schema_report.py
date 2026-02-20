from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import (
    export_report,
    generate_html_report,
    generate_markdown_report,
)

router = APIRouter(prefix="/schema-report", tags=["schema-report"])


# ----------------------------------------------------------------------
# Graph loader (API version)
# ----------------------------------------------------------------------
def get_graph() -> AssetRelationshipGraph:
    """
    Create and return an AssetRelationshipGraph populated from the default asset source.
    
    Initializes a new AssetRelationshipGraph and calls its asset-loading routine so the returned graph is ready for reporting or inspection.
    
    Returns:
        AssetRelationshipGraph: A graph instance with assets loaded from the configured source.
    """
    graph = AssetRelationshipGraph()
    graph.initialize_assets_from_source()
    return graph


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/", summary="Get schema report")
def schema_report(
    report_format: str = Query("md", pattern="^(md|html)$"),
) -> str:
    """
    Generate a schema report in the requested format.
    
    Parameters:
        report_format (str): "md" to return Markdown or "html" to return HTML. Defaults to "md" and is validated to only accept "md" or "html".
    
    Returns:
        str: Markdown string when `report_format` is "md".
        HTMLResponse: HTMLResponse containing HTML when `report_format` is "html".
    
    Raises:
        HTTPException: If an unsupported format is provided.
    """
    graph = get_graph()

    if report_format == "md":
        return generate_markdown_report(graph)
    if report_format == "html":
        html = generate_html_report(graph)
        return HTMLResponse(content=html)

    # Should never be reached due to validator above
    raise HTTPException(status_code=400, detail="Unsupported format")


@router.get("/raw", summary="Raw export of schema report")
def schema_report_raw(
    fmt: str = Query("md", pattern="^(md|html)$"),
) -> dict[str, str]:
    """
    Return a serialized schema report suitable for downloading.
    
    Parameters:
        fmt (str): Output format, either "md" for Markdown or "html" for HTML.
    
    Returns:
        dict: A payload with keys:
            - "filename" (str): Suggested filename in the form "schema_report.{fmt}".
            - "content" (str): Serialized report content in the requested format.
    """
    graph = get_graph()
    content = export_report(graph, fmt=fmt)

    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }