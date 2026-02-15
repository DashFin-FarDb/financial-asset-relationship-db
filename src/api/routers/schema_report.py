from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

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
    Replace this with your production graph loader.
    """
    graph = AssetRelationshipGraph()
    graph.initialize_assets_from_source()
    return graph


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/", summary="Get schema report", response_class=PlainTextResponse)
def schema_report(format: str = Query("md", regex="^(md|html)$")):
    """
    Return the schema report in Markdown or HTML format.
    """
    graph = get_graph()

    if format == "md":
        return generate_markdown_report(graph)
    if format == "html":
        html = generate_html_report(graph)
        return HTMLResponse(content=html)

    # Should never be reached due to validator above
    raise HTTPException(status_code=400, detail="Unsupported format")


@router.get("/raw", summary="Raw export of schema report")
def schema_report_raw(
    fmt: str = Query("md", regex="^(md|html)$"),
):
    """
    Return the schema report as a downloadable file payload.
    """
    graph = get_graph()
    try:
        content = export_report(graph, fmt=fmt)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid format.")

    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }
