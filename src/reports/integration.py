# src/reports/integration.py
from __future__ import annotations

import importlib
from typing import Any, Callable, Literal

import bleach  # type: ignore[import-untyped]
import markdown

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.schema_report import generate_schema_report

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
    Convert Markdown to sanitized HTML for safe display.

    Renders the provided Markdown to HTML, sanitizes it using the module allowlists, and post-processes links to add safe attributes (e.g., `rel="nofollow noopener"`, `target="_blank"`) while avoiding linkification inside code blocks.

    Parameters:
        md (str): Markdown content to convert.

    Returns:
        str: Sanitized HTML produced from the input Markdown.
    """
    """
    Ensure the `rel` attribute includes "noopener" for linkified elements.

    Parameters:
        attrs (dict): Bleach linkify attribute mapping; updated in-place so the `(None, 'rel')` entry includes `"noopener"` if it was not already present.
        _new (bool): Ignored placeholder to match the bleach callback signature.

    Returns:
        dict: The same `attrs` mapping with the `rel` value updated to include `"noopener"`.
    """
    """
    Ensure the `rel` attribute value includes "noopener".

    Parameters:
        attrs (dict): Mapping of attribute keys (typically tuples like `(None, "rel")`) to their values; modified in-place and returned.
        _new (bool): Unused placeholder to match the callback signature expected by Bleach.

    Returns:
        dict: The same `attrs` mapping with the `rel` value updated to include "noopener" if it was not already present.
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
    def _add_noopener(attrs: dict, _new: bool = False) -> dict:
        """
        Ensure the 'rel' attribute in a bleach.linkify attribute mapping includes "noopener".

        Modifies the provided attrs mapping in-place to append "noopener" to the (None, "rel") entry if it is not already present.

        Parameters:
            attrs (dict): Attribute mapping used by bleach.linkify (keys are typically tuples like (None, "rel")).
            _new (bool): Ignored; present only to match bleach's callback signature.

        Returns:
            dict: The same attrs mapping with the (None, "rel") value updated to include "noopener".
        """
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


def generate_markdown_report(graph: AssetRelationshipGraph) -> str:
    """
    Produce a Markdown schema report for an asset relationship graph.

    Parameters:
        graph (AssetRelationshipGraph): The asset relationship graph to generate the report from.

    Returns:
        str: The report rendered as Markdown.
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


def export_report(graph: object, fmt: ReportFormat = "md") -> str:
    """
    Export a schema report for the provided asset relationship graph in Markdown or sanitized HTML.

    Parameters:
        graph (object): Must be an AssetRelationshipGraph; a TypeError is raised if a different type is passed.
        fmt (ReportFormat): Output format, either "md" for Markdown or "html" for sanitized HTML; comparison is case-insensitive.

    Returns:
        str: Report content formatted as requested.

    Raises:
        TypeError: If `graph` is not an AssetRelationshipGraph.
        ValueError: If `fmt` is not "md" or "html".
    """
    if not isinstance(graph, AssetRelationshipGraph):
        raise TypeError(f"export_report() expected AssetRelationshipGraph, got {type(graph)!r}")

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
        html (bool): If ``True``, returns sanitized HTML; otherwise returns Markdown.

    Returns:
        Callable[[], str]: Zero-argument function producing the report string.

    Raises:
        Any exception propagated from ``graph_provider()``, ``generate_html_report()``,
        or ``generate_markdown_report()`` when the returned callable is invoked.
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
    Create a Gradio component that displays the current schema report.

    Parameters:
        graph_provider (Callable[[], AssetRelationshipGraph]): Zero-argument callable that returns the current AssetRelationshipGraph.
        html (bool): If True, produce an HTML-rendered component; otherwise produce a Markdown-rendered component.

    Returns:
        A gr.HTML component when html is True, otherwise a gr.Markdown component.

    Raises:
        RuntimeError: If Gradio is not installed.
    """
    try:
        gr = importlib.import_module("gradio")
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("Gradio is not installed.") from exc

    report_fn = make_gradio_report_fn(graph_provider, html=html)

    if html:
        return gr.HTML(value=report_fn)
    return gr.Markdown(value=report_fn)
