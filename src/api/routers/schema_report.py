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
    Create and return an AssetRelationshipGraph populated from the configured source.
    
    Returns:
        AssetRelationshipGraph: A graph instance with assets initialized from the default/configured source.
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
    Produce the schema report for the current asset graph.
    
    Parameters:
        report_format (str): Report format to produce; either "md" for Markdown or "html" for HTML.
    
    Returns:
        If `report_format` is "md", a `str` containing the Markdown report.
        If `report_format` is "html", an `HTMLResponse` containing the rendered HTML report.
    
    Raises:
        HTTPException: Raised with status code 400 if an unsupported format is provided.
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
    Provide the schema report as a downloadable payload in the requested format.
    
    Parameters:
        fmt (str): Report format, either "md" for Markdown or "html" for HTML.
    
    Returns:
        dict[str, str]: A payload with keys:
            - `filename`: the suggested filename (e.g., "schema_report.md" or "schema_report.html"),
            - `content`: the exported report content as a string.
    """
    graph = get_graph()
    content = export_report(graph, fmt=fmt)

    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }