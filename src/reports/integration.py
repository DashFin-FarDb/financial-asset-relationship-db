# src/reports/integration.py
from __future__ import annotations

from typing import Any, Callable, Literal

import bleach
import markdown

from src.logic.asset_graph import AssetRelationshipGraph

# ---------------------------------------------------------------------------
# Markdown → HTML transformation (sanitized)
# ---------------------------------------------------------------------------

# Conservative allowlist. Expand only if you have a concrete rendering need.
_ALLOWED_TAGS: set[str] = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {
        "p",
        "br",
        "hr",
        "pre",
        "code",
        "blockquote",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "span",
    }
)

_ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    # links
    "a": ["href", "title", "rel"],
    # code blocks (some markdown renderers add class for highlighting)
    "code": ["class"],
    "pre": ["class"],
    # table formatting
    "th": ["colspan", "rowspan", "align"],
    "td": ["colspan", "rowspan", "align"],
    # very limited span usage
    "span": ["class"],
}

_ALLOWED_PROTOCOLS: frozenset[str] = frozenset({"http", "https", "mailto"})


def markdown_to_html(md: str) -> str:
    """
    Render a Markdown-formatted string to sanitized HTML.

    Markdown rendering can emit raw HTML if the source contains it. We therefore
    sanitize the resulting HTML to prevent script injection (XSS).

    Parameters:
        md (str): Markdown content.

    Returns:
        str: Sanitized HTML string rendered from the provided Markdown.

    Raises:
        ValueError: If Markdown rendering or sanitisation fails.
    """
    rendered = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "toc"],
        output_format="html5",
    )

    sanitized = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )

    # Add rel="nofollow noopener" to links and open in new tab defensively.
    def _add_noopener(attrs, new=False):
        rel = attrs.get((None, "rel"), "")
        if "noopener" not in rel:
            attrs[(None, "rel")] = (rel + " noopener").strip()
        return attrs

    sanitized = bleach.linkify(
        sanitized,
        callbacks=[
            bleach.callbacks.nofollow,
            bleach.callbacks.target_blank,
            _add_noopener,
        ],
        skip_tags={"pre", "code"},
    )
    return sanitized


# ---------------------------------------------------------------------------
# Core generation interface
# ---------------------------------------------------------------------------

from src.reports.schema_report import generate_schema_report


def generate_markdown_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a Markdown schema report for the provided graph.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to report on.

    Returns:
        str: Markdown-formatted schema report.

    Raises:
        ValueError: Propagated from report generation if the graph is invalid.
    """
    return generate_schema_report(graph)


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a schema report for the provided asset relationship graph and
    return it as sanitized HTML.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to report on.

    Returns:
        str: Sanitized HTML string containing the generated report.

    Raises:
        ValueError: Propagated from report generation if the graph is invalid.
    """
    md = generate_markdown_report(graph)
    return markdown_to_html(md)


ReportFormat = Literal["md", "html"]


def export_report(graph: AssetRelationshipGraph, fmt: ReportFormat = "md") -> str:
    """
    Export a schema report for `graph` in the requested format.

    This provides a single integration point for API routes or other callers
    that need either Markdown or HTML output.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to report on.
        fmt (Literal["md", "html"]): Output format.

    Returns:
        str: Report content in the requested format.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph.
        ValueError: If `fmt` is unsupported.
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(
            f"export_report() expected AssetRelationshipGraph, got {type(graph)!r}"
        )

    fmt_norm = fmt.lower()

    if fmt_norm == "md":
        return generate_markdown_report(graph)

    if fmt_norm == "html":
        # HTML path is always sanitized via markdown_to_html()
        return generate_html_report(graph)

    raise ValueError(f"Unsupported report format: {fmt!r}. Expected 'md' or 'html'.")


def make_gradio_report_fn(
    graph_provider: Callable[[], AssetRelationshipGraph],
    html: bool = False,
) -> Callable[[], str]:
    """
    Create a no-argument callable that returns a schema report as Markdown or HTML.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Zero-argument factory
            returning the current graph.
        html (bool): If True, returns sanitized HTML; otherwise returns Markdown.

    Returns:
        Callable[[], str]: Zero-argument function producing the report string.
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
    Create and return a Gradio component pre-populated with a schema report.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Zero-argument factory
            returning the current graph.
        html (bool): If True, returns a gr.HTML component; otherwise gr.Markdown.

    Returns:
        Any: A gr.HTML or gr.Markdown Gradio component.

    Raises:
        RuntimeError: If Gradio is not installed.
    """
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Gradio is not installed.") from exc

    report_fn = make_gradio_report_fn(graph_provider, html=html)

    if html:
        return gr.HTML(report_fn())
    return gr.Markdown(report_fn())
