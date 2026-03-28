from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response

from src.api.dependencies import get_graph
from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import export_report, generate_html_report, generate_markdown_report

router = APIRouter(prefix="/schema-report", tags=["schema-report"])


@router.get("/", summary="Get schema report")
def schema_report(
    report_format: str = Query("md", pattern="^(md|html)$"),
    graph: AssetRelationshipGraph = Depends(get_graph),
) -> Response:
    """
    Return the schema report in Markdown or HTML format.
    """
    if report_format == "md":
        return Response(
            content=generate_markdown_report(graph),
            media_type="text/markdown; charset=utf-8",
        )
    html = generate_html_report(graph)
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/raw", summary="Raw export of schema report")
def schema_report_raw(
    fmt: str = Query("md", pattern="^(md|html)$"),
    graph: AssetRelationshipGraph = Depends(get_graph),
) -> dict[str, str]:
    """
    Return the schema report as a downloadable file payload.
    """
    content = export_report(graph, fmt=fmt)
    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }
