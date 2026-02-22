# src/reports/integration.py
from __future__ import annotations

from typing import Any, Callable

import markdown
import bleach

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

_ALLOWED_PROTOCOLS: list[str] = ["http", "https", "mailto"]


def markdown_to_html(md: str) -> str:
    """
    Render a Markdown-formatted string to sanitized HTML.

    Markdown rendering can emit raw HTML if the source contains it. We therefore
    sanitize the resulting HTML to prevent script injection (XSS).

    Parameters:
        md (str): Markdown content.

    Returns:
        str: Sanitized HTML string rendered from the provided Markdown.
    """
    rendered = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "toc"],
        output_format="html5",
    )

    sanitized = bleach.clean(
        rendered,
        tags=list(_ALLOWED_TAGS),
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )

    # Add rel="nofollow noopener" to links defensively.
    sanitized = bleach.linkify(
        sanitized,
        callbacks=[bleach.callbacks.nofollow, bleach.callbacks.target_blank],
        skip_tags=["pre", "code"],
    )
    return sanitized


# ---------------------------------------------------------------------------
# Core generation interface
# ---------------------------------------------------------------------------

from src.reports.schema_report import generate_schema_report


def generate_markdown_report(graph: AssetRelationshipGraph) -> str:
    """Thin wrapper around generate_schema_report for naming consistency."""
    return generate_schema_report(graph)


def generate_html_report(graph: AssetRelationshipGraph) -> str:
    """
    Generate a schema report for the provided asset relationship graph and return it as sanitized HTML.

    Returns:
        str: Sanitized HTML string containing the generated report.
    """
    md = generate_markdown_report(graph)
    return markdown_to_html(md)


def make_gradio_report_fn(
    graph_provider: Callable[[], AssetRelationshipGraph],
    html: bool = False,
) -> Callable[[], str]:
    """
    Create a no-argument function that returns a schema report as Markdown or HTML.
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
    Attach a report-generating component to a Gradio interface.
    """
    try:
        import gradio as gr
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Gradio is not installed.") from exc

    report_fn = make_gradio_report_fn(graph_provider, html=html)

    if html:
        # generate_html_report() is now sanitized
        return gr.HTML(report_fn())
    return gr.Markdown(report_fn())
