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
    Convert Markdown source into an HTML string.
    
    Parameters:
        md (str): Markdown source to convert.
    
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
    Generate a Markdown-formatted schema and metrics report for the provided asset relationship graph.
    
    Parameters:
        graph (AssetRelationshipGraph): The graph whose schema and metrics will be included in the report.
    
    Returns:
        str: Markdown string containing the generated report.
    """
    generator = SchemaReportGenerator(graph)
    return generator.generate()


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate an HTML schema and metrics report from the provided graph.
    
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
    Create a zero-argument callable for Gradio that produces a schema report in Markdown or HTML.
    
    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Function that returns an initialized AssetRelationshipGraph when called.
        html (bool): If True the callable returns an HTML report; otherwise it returns a Markdown report.
    
    Returns:
        Callable[[], str]: A zero-argument function that returns the report as a string (HTML if `html` is True, Markdown otherwise).
    """

    def _fn() -> str:
        """
        Return the current schema report for the graph provided by the enclosing graph_provider.
        
        The callable retrieves the latest AssetRelationshipGraph from the closure's graph_provider and returns the report formatted as HTML if the enclosing factory was configured for HTML, otherwise as Markdown.
        
        Returns:
            str: The report string — HTML when the creator requested HTML, otherwise Markdown.
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
    Attach a generated schema report to a Gradio Blocks or Interface component.
    
    Lazily imports Gradio and returns a component that renders the report produced
    from the provided graph provider. The returned component is HTML when
    `html=True`, otherwise Markdown.
    
    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): A zero-argument callable that returns the graph used to generate the report.
        html (bool): If `True`, produce an HTML component; if `False`, produce a Markdown component.
    
    Returns:
        A Gradio component that renders the report as HTML when `html=True`, otherwise as Markdown.
    
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
    Embed the schema Markdown report from the given graph into the Plotly figure's metadata under the key "schema_report".
    
    Parameters:
        fig (Any): A Plotly figure (or figure-like dict) whose `metadata` will be created or updated; mutated in place.
        graph (AssetRelationshipGraph): Source graph used to generate the Markdown schema report.
    
    Returns:
        Any: The same figure object with `metadata["schema_report"]` set to the generated Markdown report.
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
    Export the schema and metrics report for a graph in the requested format.
    
    Supported formats:
    - "md": returns the report as a Markdown string.
    - "html": returns the report as an HTML string.
    
    Parameters:
        graph (AssetRelationshipGraph): The graph to generate the report for.
        fmt (str, optional): Desired output format; case-insensitive. Defaults to "md".
    
    Returns:
        str: The report in the requested format ("md" → Markdown, "html" → HTML).
    
    Raises:
        ValueError: If `fmt` is not one of the supported formats.
    """
    fmt_normalized = fmt.lower().strip()

    if fmt_normalized == "md":
        return generate_markdown_report(graph)

    if fmt_normalized == "html":
        return generate_html_report(graph)

    raise ValueError(f"Unsupported export format: {fmt!r}")