"""API routes for generating and validating schema reports."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query  # pylint: disable=import-error
from fastapi.responses import Response  # pylint: disable=import-error

from src.api.dependencies import get_graph
from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import (
    export_report,
    generate_html_report,
    generate_markdown_report,
)

router = APIRouter(prefix="/schema-report", tags=["schema-report"])


@router.get("/", summary="Get schema report")
def schema_report(
    graph: Annotated[AssetRelationshipGraph, Depends(get_graph)],
    report_format: Annotated[
        Literal["md", "html"],
        Query(pattern="^(md|html)$"),
    ] = "md",
) -> Response:
    """
    Serve the schema report as Markdown or HTML.
    
    Parameters:
        report_format (Literal["md", "html"]): Desired output format — `"md"` returns Markdown, `"html"` returns HTML.
    
    Returns:
        Response: HTTP response containing the report content; media type is `text/markdown; charset=utf-8` for `md` and `text/html; charset=utf-8` for `html`.
    """
    if report_format == "md":
        return Response(
            content=generate_markdown_report(graph),
            media_type="text/markdown; charset=utf-8",
        )
    html = generate_html_report(graph)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/raw", summary="Raw export of schema report")
def schema_report_raw(
    graph: Annotated[AssetRelationshipGraph, Depends(get_graph)],
    fmt: Annotated[Literal["md", "html"], Query(pattern="^(md|html)$")] = "md",
) -> dict[str, str]:
    """
    Produce a downloadable schema report payload in the requested format.
    
    Parameters:
    	fmt (Literal["md", "html"]): Report format; "md" for Markdown or "html" for HTML.
    
    Returns:
    	payload (dict[str, str]): A mapping with keys:
    		- "filename": Suggested download filename (e.g., "schema_report.md" or "schema_report.html").
    		- "content": The report content as a string in the requested format.
    """
    content = export_report(graph, fmt=fmt)
    return {
        "filename": f"schema_report.{fmt}",
        "content": content,
    }
