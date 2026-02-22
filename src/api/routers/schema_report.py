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
    Load and return an AssetRelationshipGraph populated from the configured asset source.

    Returns:
        AssetRelationshipGraph: Graph instance with assets initialized from the configured source.
    """
    graph = AssetRelationshipGraph()
    graph.initialize_assets_from_source()
    return graph


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


from typing import Union

from fastapi.responses import HTMLResponse, Response


@router.get("/", summary="Get schema report")
def schema_report(
    report_format: str = Query("md", pattern="^(md|html)$"),
) -> Response:
    """
    Produce a schema report for the current asset relationship graph in either Markdown or HTML.

    Parameters:
        report_format (str): Format of the report; must be "md" for Markdown or "html" for HTML.

    Returns:
        When `report_format` is "md", a `str` containing the Markdown report; when `report_format` is "html", an `HTMLResponse` containing the rendered HTML.

    Raises:
        HTTPException: If an unsupported `report_format` is provided.
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
    Produce a raw export payload of the schema report in the requested format.

    Parameters:
        fmt (str): Output format, either "md" for Markdown or "html" for HTML.

    Returns:
        dict[str, str]: A payload containing:
                - "filename": suggested filename for download (e.g., "schema_report.md" or "schema_report.html")
                - "content": the report content as a string in the requested format
    """
    graph = get_graph()
    content = export_report(graph, fmt=fmt)

    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }
