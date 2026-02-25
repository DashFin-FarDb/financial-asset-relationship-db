from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from src.data.sample_data import create_sample_database
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
    """Return an initialised graph using sample data."""
    return create_sample_database()


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/", summary="Get schema report")
def schema_report(
    report_format: str = Query("md", pattern="^(md|html)$"),
) -> str:
    """
    Return the schema report in Markdown or HTML format.
    """
    graph = get_graph()

    if report_format == "md":
        return generate_markdown_report(graph)
    html = generate_html_report(graph)
    return HTMLResponse(content=html)


@router.get("/raw", summary="Raw export of schema report")
def schema_report_raw(
    fmt: str = Query("md", pattern="^(md|html)$"),
) -> dict[str, str]:
    """
    Return the schema report as a downloadable file payload.
    """
    graph = get_graph()
    content = export_report(graph, fmt=fmt)

    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }
