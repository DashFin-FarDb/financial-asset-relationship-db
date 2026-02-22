from __future__ import annotations

from typing import Any, Callable, Optional

import markdown

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report_generator import SchemaReportGenerator

# ---------------------------------------------------------------------------
# Markdown → HTML transformation
# ---------------------------------------------------------------------------


def markdown_to_html(md: str) -> str:
    """
    Render a Markdown-formatted string to HTML.

    Returns:
        html (str): HTML string rendered from the provided Markdown.
    """
    return markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "toc"],
        output_format="html5",
    )


# ---------------------------------------------------------------------------
# Core generation interface
# ---------------------------------------------------------------------------


from src.reports.schema_report import generate_schema_report


def generate_markdown_report(graph: AssetRelationshipGraph) -> str:
    """Thin wrapper around generate_schema_report for naming consistency."""
    return generate_schema_report(graph)


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a schema report for the provided asset relationship graph and return it as HTML.

    Returns:
        html (str): HTML string containing the generated report.
    """
    md = generate_markdown_report(graph)
    return markdown_to_html(md)


# ---------------------------------------------------------------------------
# Optional Gradio integration

# ---------------------------------------------------------------------------


def make_gradio_report_fn(
    graph_provider: Callable[[], AssetRelationshipGraph],
    html: bool = False,
) -> Callable[[], str]:
    """
    Create a no-argument function that returns a schema report as Markdown or HTML.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Callable that returns an AssetRelationshipGraph used to generate the report.
        html (bool): If True, the returned function produces an HTML report; otherwise it produces a Markdown report.

    Returns:
        Callable[[], str]: A no-argument callable that returns the generated report as a string — Markdown when `html` is False, HTML when `html` is True.
    """

    def _fn() -> str:
        """
        Produce a schema report from the current AssetRelationshipGraph in the selected format.

        Returns:
            report (str): The report as a string — HTML when configured for HTML, otherwise Markdown.
        """
        graph = graph_provider()
        if html:
            return generate_html_report(graph)
        return generate_markdown_report(graph)

    return _fn


def attach_to_gradio_interface(
    graph_provider: Callable[[], AssetRelationshipGraph],
    html: bool = False,
) -> Any:
    """
    Attach a report-generating component to a Gradio interface.

    Creates and returns a Gradio component that displays the report produced by the given graph provider; returns an HTML component when `html` is True, otherwise a Markdown component.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): A zero-argument callable that returns the graph from which the report will be generated.
        html (bool): If True, produce an HTML component; if False, produce a Markdown component.

    Returns:
        Any: A Gradio component that renders the report (HTML if `html` is True, otherwise Markdown).

    Raises:
        RuntimeError: If Gradio is not installed.
    """
    try:
        import gradio as gr
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Gradio is not installed.") from exc

    report_fn = make_gradio_report_fn(graph_provider, html=html)

    if html:
        return gr.HTML(report_fn())
    return gr.Markdown(report_fn())


# ---------------------------------------------------------------------------

# Plotly integration helpers
# ---------------------------------------------------------------------------


def embed_report_in_plotly_figure(
    fig: Any,
    graph: AssetRelationshipGraph,
) -> Any:
    """
    Embed the generated schema report into a Plotly figure's metadata.

    The generated Markdown report is stored on the figure under the key
    `fig["metadata"]["schema_report"]`.

    Parameters:
        fig (Any): A Plotly figure-like mapping; will be mutated to include metadata.
        graph (AssetRelationshipGraph): The asset relationship graph used to generate the report.

    Returns:
        Any: The same figure object with the `metadata` entry updated to include the schema report.
    """
    md = generate_markdown_report(graph)
    fig["metadata"] = fig.get("metadata", {})
    fig["metadata"]["schema_report"] = md
    return fig


# ---------------------------------------------------------------------------
# Export utilities
# ---------------------------------------------------------------------------


def export_report(
    graph: AssetRelationshipGraph,
    *,
    fmt: str = "md",
) -> str:
    """
    Export a schema report in the requested format.

    Parameters:
        graph (AssetRelationshipGraph): Asset relationship graph used to generate the report.
        fmt (str): Output format, either "md" for Markdown or "html" for HTML (case-insensitive).

    Returns:
        str: The report as a string in the requested format.

    Raises:
        ValueError: If an unsupported `fmt` value is provided.
    """
    fmt_normalized = fmt.lower().strip()

    if fmt_normalized == "md":
        return generate_markdown_report(graph)

    if fmt_normalized == "html":
        return generate_html_report(graph)

    raise ValueError(f"Unsupported export format: {fmt!r}")
