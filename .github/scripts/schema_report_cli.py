#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import (
    export_report,
    generate_html_report,
    generate_markdown_report,
)

app = typer.Typer(add_completion=False)


# ----------------------------------------------------------------------
# Graph loader placeholder
# ----------------------------------------------------------------------
def load_graph() -> AssetRelationshipGraph:
    """
    Create and return a new AssetRelationshipGraph instance.
    
    Returns:
        AssetRelationshipGraph: A newly constructed AssetRelationshipGraph ready for use (placeholder loader; replace with project-specific loading logic if needed).
    """
    graph = AssetRelationshipGraph()
    return graph


# ----------------------------------------------------------------------
# CLI Commands
# ----------------------------------------------------------------------
@app.command("md")
def generate_md() -> None:
    """Print the Markdown schema report to stdout."""
    graph = load_graph()
    md = generate_markdown_report(graph)
    typer.echo(md)


@app.command("html")
def generate_html() -> None:
    """Print the HTML schema report to stdout."""
    graph = load_graph()
    html = generate_html_report(graph)
    typer.echo(html)


@app.command("save")
def save_report(
    out: Path = typer.Argument(..., help="Output file path"),
    fmt: str = typer.Option("md", help="Output format: md or html"),
) -> None:
    """
    Write the generated schema report to the specified file.
    
    Parameters:
        out (Path): Destination file path where the report will be written; existing files will be overwritten.
        fmt (str): Output format, either "md" for Markdown or "html" for HTML.
    """
    graph = load_graph()
    content = export_report(graph, fmt=fmt)
    out.write_text(content, encoding="utf-8")
    typer.echo(f"Report written to {out}")


def main() -> None:
    """
    Run the CLI application.
    
    Starts the Typer app; on any unexpected exception it prints an error message to stderr and exits the process with status code 1.
    """
    try:
        app()
    except Exception as exc:  # pragma: no cover
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()