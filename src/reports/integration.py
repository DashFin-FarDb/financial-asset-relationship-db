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
    Convert a Markdown string to HTML.

    Returns:
        html (str): HTML representation of the provided Markdown.
    """
    return markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "toc"],
        output_format="html5",
    )


# ---------------------------------------------------------------------------
# Core generation interface
# ---------------------------------------------------------------------------


def generate_markdown_report(graph: AssetRelationshipGraph) -> str:
    """
    Create a Markdown-formatted schema and metrics report for the given asset relationship graph.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to generate the report from.

    Returns:
        report_md (str): Markdown string containing the combined schema and metrics report.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Produce an HTML-formatted schema and metrics report for the given asset relationship graph.

    Parameters:
        graph (AssetRelationshipGraph): The graph containing assets and relationships to include in the report.

    Returns:
        html (str): The report rendered as an HTML string.
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
    Create a zero-argument callable for use with Gradio that produces a schema report.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Function that returns the AssetRelationshipGraph to report on.
        html (bool): If True, the returned callable produces an HTML report; otherwise it produces a Markdown report.

    Returns:
        Callable[[], str]: A no-argument function that returns the generated report as HTML when `html` is True, otherwise as Markdown.
    """

    def _fn() -> str:
        """
        Produce a schema report from the current graph provider, returning HTML when the `html` flag is set and Markdown otherwise.

        Returns:
            str: The report as a string — HTML if `html` is set, otherwise Markdown.
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
    Create a Gradio component that displays a schema report produced from a provided graph.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Function called to obtain the graph when the component is rendered.
        html (bool): If True, produce a Gradio HTML component; otherwise produce a Gradio Markdown component.

    Returns:
        A Gradio component (HTML or Markdown) that, when shown, contains the generated report.

    Raises:
        RuntimeError: If Gradio cannot be imported.
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
    Embed the Markdown schema report into a Plotly figure's metadata.

    Parameters:
        fig (Any): A Plotly figure-like mapping (dict-like) that will receive metadata.
        graph (AssetRelationshipGraph): The asset relationship graph used to generate the Markdown report.

    Returns:
        Any: The same figure object with a `metadata` dictionary where the key `schema_report` contains the generated Markdown report.
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
    Produce the report in the requested format.

    Parameters:
        fmt (str): Output format, either "md" for Markdown or "html" for HTML.

    Returns:
        The report as a string formatted according to `fmt` ("md" or "html").

    Raises:
        ValueError: If `fmt` is not one of the supported formats.
    """
    fmt_normalized = fmt.lower().strip()

    if fmt_normalized == "md":
        return generate_markdown_report(graph)

    if fmt_normalized == "html":
        return generate_html_report(graph)

    raise ValueError(f"Unsupported export format: {fmt!r}")
