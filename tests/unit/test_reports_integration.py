# ruff: noqa: S101
"""Unit tests for src/reports/integration.py report integration module.

This module tests the report generation and integration functions including:
- Markdown to HTML conversion
- Report generation functions
- Gradio integration helpers
- Plotly integration helpers
- Export utilities
"""

from unittest.mock import MagicMock, patch

import pytest

from src.logic.asset_graph import AssetRelationshipGraph
from src.reports.integration import (
    attach_to_gradio_interface,
    embed_report_in_plotly_figure,
    export_report,
    generate_html_report,
    generate_markdown_report,
    make_gradio_report_fn,
    markdown_to_html,
)


@pytest.mark.unit
class TestMarkdownToHtml:
    """Test cases for markdown to HTML conversion."""

    @staticmethod
    def test_markdown_to_html_basic_conversion() -> None:
        """Test basic markdown to HTML conversion."""
        md = "# Heading\n\nParagraph text."
        html = markdown_to_html(md)

        # Markdown library adds id attributes to headings
        assert "Heading" in html
        assert "<p>Paragraph text.</p>" in html

    @staticmethod
    def test_markdown_to_html_with_tables() -> None:
        """Test markdown to HTML conversion with tables."""
        md = """
| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
"""
        html = markdown_to_html(md)

        assert "<table>" in html and "<tr>" in html and "<td>" in html
        assert "<th>Column 1</th>" in html
        assert "<td>Value 1</td>" in html

    @staticmethod
    def test_markdown_to_html_with_code_blocks() -> None:
        """Test markdown to HTML conversion with fenced code blocks."""
        md = """
```python
def hello():
    print("Hello")
```
"""
        html = markdown_to_html(md)

        # Code is wrapped in pre and code tags
        assert "code" in html
        assert "hello()" in html

    @staticmethod
    def test_markdown_to_html_empty_string() -> None:
        """Test markdown to HTML with empty string."""
        md = ""
        html = markdown_to_html(md)
        assert html == ""

    @staticmethod
    def test_markdown_to_html_with_special_characters() -> None:
        """Test markdown to HTML with special characters."""
        md = "# Report with & < > characters"
        html = markdown_to_html(md)

        # HTML entities should be properly escaped
        assert "&amp;" in html
        assert "Report with" in html


@pytest.mark.unit
class TestGenerateReports:
    """Test cases for report generation functions."""

    @staticmethod
    def test_generate_markdown_report() -> None:
        """Test markdown report generation."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with patch(
            "src.reports.integration.SchemaReportGenerator"
        ) as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator.generate.return_value = "# Test Report"
            mock_generator_class.return_value = mock_generator

            result = generate_markdown_report(mock_graph)

            assert result == "# Test Report"
            mock_generator_class.assert_called_once_with(mock_graph)
            mock_generator.generate.assert_called_once()

    @staticmethod
    def test_generate_html_report() -> None:
        """Test HTML report generation."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with (
            patch(
                "src.reports.integration.SchemaReportGenerator"
            ) as mock_generator_class,
            patch("src.reports.integration.markdown_to_html") as mock_md_to_html,
        ):
            mock_generator = MagicMock()
            mock_generator.generate.return_value = "# Test Report"
            mock_generator_class.return_value = mock_generator
            mock_md_to_html.return_value = "<h1>Test Report</h1>"

            result = generate_html_report(mock_graph)

            assert result == "<h1>Test Report</h1>"
            mock_md_to_html.assert_called_once_with("# Test Report")

    @staticmethod
    def test_generate_reports_with_empty_graph() -> None:
        """Test report generation with empty graph."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        mock_graph.assets = {}
        mock_graph.relationships = {}

        with patch(
            "src.reports.integration.SchemaReportGenerator"
        ) as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator.generate.return_value = "# Empty Report"
            mock_generator_class.return_value = mock_generator

            result = generate_markdown_report(mock_graph)

            assert "Empty Report" in result


@pytest.mark.unit
class TestGradioIntegration:
    """Test cases for Gradio integration helpers."""

    @staticmethod
    def test_make_gradio_report_fn_markdown() -> None:
        """Test Gradio report function creation for markdown."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        def graph_provider():
            """Provides a mock AssetRelationshipGraph for testing."""
            return mock_graph

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Gradio Report"

            fn = make_gradio_report_fn(graph_provider, html=False)
            result = fn()

            assert result == "# Gradio Report"
            mock_gen_md.assert_called_once_with(mock_graph)

    @staticmethod
    def test_make_gradio_report_fn_html() -> None:
        """Test Gradio report function creation for HTML."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        def graph_provider():
            """Provide the mock AssetRelationshipGraph instance for testing."""
            return mock_graph

        with patch("src.reports.integration.generate_html_report") as mock_gen_html:
            mock_gen_html.return_value = "<h1>Gradio Report</h1>"

            fn = make_gradio_report_fn(graph_provider, html=True)
            result = fn()

            assert result == "<h1>Gradio Report</h1>"
            mock_gen_html.assert_called_once_with(mock_graph)

    @staticmethod
    def test_attach_to_gradio_interface_markdown() -> None:
        """Test attaching markdown report to Gradio interface."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        def graph_provider():
            """Provide a mock AssetRelationshipGraph instance for testing."""
            return mock_graph

        with (
            patch("src.reports.integration.generate_markdown_report") as mock_gen_md,
            patch("gradio.Markdown") as mock_markdown,
        ):
            mock_gen_md.return_value = "# Report"
            mock_markdown.return_value = MagicMock()

            result = attach_to_gradio_interface(graph_provider, html=False)

            assert result is not None
            mock_markdown.assert_called_once()

    @staticmethod
    def test_attach_to_gradio_interface_html() -> None:
        """Test attaching HTML report to Gradio interface."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        def graph_provider():
            """Provide the graph for testing by returning a mock graph."""
            return mock_graph

        with (
            patch("src.reports.integration.generate_html_report") as mock_gen_html,
            patch("gradio.HTML") as mock_html,
        ):
            mock_gen_html.return_value = "<h1>Report</h1>"
            mock_html.return_value = MagicMock()

            result = attach_to_gradio_interface(graph_provider, html=True)

            assert result is not None
            mock_html.assert_called_once()

    @staticmethod
    def test_attach_to_gradio_interface_missing_gradio() -> None:
        """Test that missing Gradio raises RuntimeError."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        def graph_provider():
            """Provide a mock AssetRelationshipGraph instance for testing when Gradio is missing."""
            return mock_graph

        with (
            patch.dict("sys.modules", {"gradio": None}),
            pytest.raises(RuntimeError, match="Gradio is not installed"),
        ):
            attach_to_gradio_interface(graph_provider)


@pytest.mark.unit
class TestPlotlyIntegration:
    """Test cases for Plotly integration helpers."""

    @staticmethod
    def test_embed_report_in_plotly_figure() -> None:
        """Test embedding report in Plotly figure metadata."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        fig = {"data": [], "layout": {}}

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Plotly Report"

            result = embed_report_in_plotly_figure(fig, mock_graph)

            assert result["metadata"]["schema_report"] == "# Plotly Report"
            mock_gen_md.assert_called_once_with(mock_graph)

    @staticmethod
    def test_embed_report_preserves_existing_metadata() -> None:
        """Test that embedding report preserves existing figure metadata."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        fig = {"data": [], "layout": {}, "metadata": {"existing": "value"}}

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Report"

            result = embed_report_in_plotly_figure(fig, mock_graph)

            assert result["metadata"]["existing"] == "value"
            assert result["metadata"]["schema_report"] == "# Report"

    @staticmethod
    def test_embed_report_in_empty_figure() -> None:
        """Test embedding report in empty Plotly figure."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        fig = {}

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Empty Fig Report"

            result = embed_report_in_plotly_figure(fig, mock_graph)

            assert "metadata" in result
            assert result["metadata"]["schema_report"] == "# Empty Fig Report"


@pytest.mark.unit
class TestExportReport:
    """Test cases for export_report utility."""

    @staticmethod
    def test_export_report_markdown() -> None:
        """Test exporting report in markdown format."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Export MD"

            result = export_report(mock_graph, fmt="md")

            assert result == "# Export MD" and isinstance(result, str)
            mock_gen_md.assert_called_once_with(mock_graph)

    @staticmethod
    def test_export_report_html() -> None:
        """Test exporting report in HTML format."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with patch("src.reports.integration.generate_html_report") as mock_gen_html:
            mock_gen_html.return_value = "<h1>Export HTML</h1>"

            result = export_report(mock_graph, fmt="html")

            assert result == "<h1>Export HTML</h1>"
            mock_gen_html.assert_called_once_with(mock_graph)

    @staticmethod
    def test_export_report_invalid_format() -> None:
        """Test that invalid format raises ValueError."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with pytest.raises(ValueError, match="Unsupported export format"):
            export_report(mock_graph, fmt="pdf")

    @staticmethod
    def test_export_report_format_normalization() -> None:
        """Test that format parameter is normalized."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Report"

            # Test with uppercase
            result = export_report(mock_graph, fmt="MD")
            assert result == "# Report"

            # Test with whitespace
            result = export_report(mock_graph, fmt=" md ")
            assert result == "# Report"

    @staticmethod
    def test_export_report_with_empty_format_string() -> None:
        """Test export with empty format string raises ValueError."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with pytest.raises(ValueError, match="Unsupported export format"):
            export_report(mock_graph, fmt="")


@pytest.mark.unit
class TestIntegrationEdgeCases:
    """Test edge cases and boundary conditions for integration module."""

    @staticmethod
    def test_markdown_to_html_with_unicode() -> None:
        """Test markdown to HTML with Unicode characters."""
        md = "# 价格 报告\n\nÜnicode tëxt: €100"
        html = markdown_to_html(md)

        assert "价格 报告" in html
        assert "Ünicode tëxt" in html
        assert "€100" in html

    @staticmethod
    def test_generate_report_with_large_graph() -> None:
        """Test report generation with large graph."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        mock_graph.assets = {f"asset_{i}": MagicMock() for i in range(1000)}

        with patch(
            "src.reports.integration.SchemaReportGenerator"
        ) as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator.generate.return_value = "# Large Report\n\n" + (
                "Content\n" * 1000
            )
            mock_generator_class.return_value = mock_generator

            result = generate_markdown_report(mock_graph)

            assert "Large Report" in result
            assert len(result) > 1000 and len(result) < 10000  # Ensure reasonable size

    @staticmethod
    def test_export_with_special_characters_in_content() -> None:
        """Test export with special characters in report content."""
        mock_graph = MagicMock(spec=AssetRelationshipGraph)

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Report\n\n&<>\"'`\n\nSpecial: €$¥£"

            result = export_report(mock_graph, fmt="md")

            assert "&<>\"'`" in result
            assert "€$¥£" in result

    @staticmethod
    def test_make_gradio_report_fn_calls_provider_each_time() -> None:
        """Test that Gradio report function calls provider each time."""
        call_count = 0

        def graph_provider():
            """Provides a mock AssetRelationshipGraph and increments the call count."""
            nonlocal call_count
            call_count += 1
            return MagicMock(spec=AssetRelationshipGraph)

        with patch("src.reports.integration.generate_markdown_report") as mock_gen_md:
            mock_gen_md.return_value = "# Report"

            fn = make_gradio_report_fn(graph_provider, html=False)

            fn()
            fn()
            fn()

            assert call_count == 3  # Provider called each time
