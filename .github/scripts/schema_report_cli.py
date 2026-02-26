#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import (
    export_report,
    generate_html_report,
    generate_markdown_report,
)


# ----------------------------------------------------------------------
# Graph loader placeholder
# ----------------------------------------------------------------------
def load_graph() -> AssetRelationshipGraph:
    """
    Return an AssetRelationshipGraph instance for report generation.

    This function creates and returns a new AssetRelationshipGraph. Replace this implementation with the application's real graph-loading logic when integrating with actual data sources.

    Returns:
        AssetRelationshipGraph: The graph instance used by the CLI reporting commands.
    """
    graph = AssetRelationshipGraph()
    return graph


# ----------------------------------------------------------------------
# CLI Commands
# ----------------------------------------------------------------------
def generate_md() -> None:
    """
    Print the Markdown-formatted schema report for the current AssetRelationshipGraph to stdout.
    """
    graph = load_graph()
    md = generate_markdown_report(graph)
    print(md)


def generate_html() -> None:
    """Print the HTML schema report to stdout."""
    graph = load_graph()
    html = generate_html_report(graph)
    print(html)


def save_report(out: Path, fmt: str = "md") -> None:
    """
    Save the generated schema report to the specified file.

    Parameters:
        out (Path): Destination file path to write the report.
        fmt (str): Output format; either "md" for Markdown or "html" for HTML.
    """
    graph = load_graph()
    content = export_report(graph, fmt=fmt)
    out.write_text(content, encoding="utf-8")
    print(f"Report written to {out}")


def main() -> None:
    """
    Run the CLI application and exit on unhandled errors.

    If the application raises an exception, print a concise error message to stderr and terminate the process with exit status 1.
    """
    parser = argparse.ArgumentParser(
        description="Generate schema reports for AssetRelationshipGraph"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # md command
    subparsers.add_parser(
        "md", help="Print the Markdown-formatted schema report to stdout"
    )

    # html command
    subparsers.add_parser("html", help="Print the HTML schema report to stdout")

    # save command
    save_parser = subparsers.add_parser(
        "save", help="Save the generated schema report to a file"
    )
    save_parser.add_argument("out", type=Path, help="Output file path")
    save_parser.add_argument(
        "--fmt",
        type=str,
        default="md",
        choices=["md", "html"],
        help="Output format: md or html (default: md)",
    )

    args = parser.parse_args()

    try:
        if args.command == "md":
            generate_md()
        elif args.command == "html":
            generate_html()
        elif args.command == "save":
            save_report(args.out, args.fmt)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
