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
    Convert a Markdown string into HTML.

    Uses python-markdown for safety and deterministic output.
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
    Generate a Markdown-formatted schema + metrics report.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate an HTML report by converting the Markdown output.
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
    Create a Gradio-friendly callable that returns either Markdown or HTML.

    Parameters:
        graph_provider: Callable returning an initialized AssetRelationshipGraph.
        html: If True, output HTML; otherwise output Markdown.

    Returns:
        A function suitable for Gradio interfaces.
    """

    def _fn() -> str:
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
    Attach a report generator to a Gradio Blocks or Interface component.

    Returns a Gradio component (Markdown or HTML), depending on parameters.

    This function avoids importing Gradio unless actually invoked, to
    prevent unnecessary dependencies from leaking into environments
    that do not use Gradio.
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
    Attach a schema report to a Plotly figure as metadata.

    This does not alter visual rendering unless the consumer UI reads
    the metadata. It keeps Plotly figures self-describing.
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
    Export the report in one of several formats.

    Supported:
        - "md"  → Markdown string
        - "html" → HTML string

    Raises:
        ValueError: For unsupported formats.
    """
    fmt_normalized = fmt.lower().strip()

    if fmt_normalized == "md":
        return generate_markdown_report(graph)

    if fmt_normalized == "html":
        return generate_html_report(graph)

    raise ValueError(f"Unsupported export format: {fmt!r}")
