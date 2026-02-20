"""Comprehensive tests for .github/scripts/schema_report_cli.py"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Import the module under test
import sys

scripts_path = Path(__file__).parent.parent.parent / ".github" / "scripts"
sys.path.insert(0, str(scripts_path))

from schema_report_cli import app, generate_html, generate_md, load_graph, main, save_report


runner = CliRunner()


class TestLoadGraph:
    """Test load_graph function."""

    @patch("schema_report_cli.AssetRelationshipGraph")
    def test_load_graph_creates_empty_graph(self, mock_graph_class):
        """Test that load_graph creates an AssetRelationshipGraph."""
        mock_instance = MagicMock()
        mock_graph_class.return_value = mock_instance

        result = load_graph()

        assert result == mock_instance
        mock_graph_class.assert_called_once()


class TestGenerateMd:
    """Test generate_md command."""

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.generate_markdown_report")
    @patch("schema_report_cli.typer.echo")
    def test_generate_md_success(self, mock_echo, mock_gen_md, mock_load):
        """Test successful markdown generation."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_gen_md.return_value = "# Test Report\n\nContent"

        result = runner.invoke(app, ["md"])

        assert result.exit_code == 0
        mock_load.assert_called_once()
        mock_gen_md.assert_called_once_with(mock_graph)
        mock_echo.assert_called_once_with("# Test Report\n\nContent")

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.generate_markdown_report")
    def test_generate_md_with_graph_data(self, mock_gen_md, mock_load):
        """Test markdown generation includes graph data."""
        mock_graph = MagicMock()
        mock_graph.assets = {"AAPL": MagicMock()}
        mock_load.return_value = mock_graph
        mock_gen_md.return_value = "# Report"

        result = runner.invoke(app, ["md"])

        assert result.exit_code == 0
        # Verify graph was passed to report generator
        mock_gen_md.assert_called_with(mock_graph)


class TestGenerateHtml:
    """Test generate_html command."""

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.generate_html_report")
    @patch("schema_report_cli.typer.echo")
    def test_generate_html_success(self, mock_echo, mock_gen_html, mock_load):
        """Test successful HTML generation."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_gen_html.return_value = "<html><body>Test</body></html>"

        result = runner.invoke(app, ["html"])

        assert result.exit_code == 0
        mock_load.assert_called_once()
        mock_gen_html.assert_called_once_with(mock_graph)
        mock_echo.assert_called_once()

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.generate_html_report")
    def test_generate_html_with_graph(self, mock_gen_html, mock_load):
        """Test HTML generation with graph."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_gen_html.return_value = "<html></html>"

        result = runner.invoke(app, ["html"])

        assert result.exit_code == 0
        mock_gen_html.assert_called_with(mock_graph)


class TestSaveReport:
    """Test save_report command."""

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    @patch("schema_report_cli.typer.echo")
    def test_save_report_markdown_default(self, mock_echo, mock_export, mock_load, tmp_path):
        """Test saving report in markdown format (default)."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_export.return_value = "# Test Report"

        output_file = tmp_path / "report.md"
        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        mock_load.assert_called_once()
        mock_export.assert_called_once_with(mock_graph, fmt="md")

        # Verify file was created
        assert output_file.exists()
        assert "Test Report" in output_file.read_text()

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    def test_save_report_html_format(self, mock_export, mock_load, tmp_path):
        """Test saving report in HTML format."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_export.return_value = "<html><body>Test</body></html>"

        output_file = tmp_path / "report.html"
        result = runner.invoke(app, ["save", str(output_file), "--fmt", "html"])

        assert result.exit_code == 0
        mock_export.assert_called_once_with(mock_graph, fmt="html")

        # Verify file content
        assert output_file.exists()
        content = output_file.read_text()
        assert "<html>" in content

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    @patch("schema_report_cli.typer.echo")
    def test_save_report_outputs_message(self, mock_echo, mock_export, mock_load, tmp_path):
        """Test that save command outputs success message."""
        mock_graph = MagicMock()
        mock_load.return_value = mock_graph
        mock_export.return_value = "Report content"

        output_file = tmp_path / "test.md"
        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        # Check that echo was called with a message containing the path
        mock_echo.assert_called()
        call_args = str(mock_echo.call_args)
        assert "Report written" in call_args or str(output_file) in call_args


class TestMain:
    """Test main function."""

    @patch("schema_report_cli.app")
    def test_main_invokes_app(self, mock_app):
        """Test that main invokes the typer app."""
        main()
        mock_app.assert_called_once()

    @patch("schema_report_cli.app")
    @patch("schema_report_cli.typer.echo")
    @patch("schema_report_cli.sys.exit")
    def test_main_handles_exception(self, mock_exit, mock_echo, mock_app):
        """Test that main handles exceptions gracefully."""
        mock_app.side_effect = ValueError("Test error")

        main()

        mock_exit.assert_called_once_with(1)
        mock_echo.assert_called()


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    @patch("schema_report_cli.AssetRelationshipGraph")
    @patch("schema_report_cli.generate_markdown_report")
    def test_md_command_end_to_end(self, mock_gen_md, mock_graph_class):
        """Test md command end-to-end."""
        mock_graph_class.return_value = MagicMock()
        mock_gen_md.return_value = "# Schema Report\n\n## Overview"

        result = runner.invoke(app, ["md"])

        assert result.exit_code == 0
        assert "# Schema Report" in result.stdout

    @patch("schema_report_cli.AssetRelationshipGraph")
    @patch("schema_report_cli.generate_html_report")
    def test_html_command_end_to_end(self, mock_gen_html, mock_graph_class):
        """Test html command end-to-end."""
        mock_graph_class.return_value = MagicMock()
        mock_gen_html.return_value = "<html><body>Report</body></html>"

        result = runner.invoke(app, ["html"])

        assert result.exit_code == 0
        assert "<html>" in result.stdout

    @patch("schema_report_cli.AssetRelationshipGraph")
    @patch("schema_report_cli.export_report")
    def test_save_command_end_to_end(self, mock_export, mock_graph_class, tmp_path):
        """Test save command end-to-end."""
        mock_graph_class.return_value = MagicMock()
        mock_export.return_value = "# Full Report Content"

        output_file = tmp_path / "output.md"
        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Full Report Content" in output_file.read_text()


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("schema_report_cli.load_graph")
    def test_md_command_handles_graph_error(self, mock_load):
        """Test md command handles graph loading error."""
        mock_load.side_effect = Exception("Graph error")

        result = runner.invoke(app, ["md"])

        # Should fail gracefully
        assert result.exit_code != 0

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.generate_markdown_report")
    def test_md_command_handles_generation_error(self, mock_gen, mock_load):
        """Test md command handles report generation error."""
        mock_load.return_value = MagicMock()
        mock_gen.side_effect = Exception("Generation error")

        result = runner.invoke(app, ["md"])

        assert result.exit_code != 0

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    def test_save_command_handles_write_error(self, mock_export, mock_load):
        """Test save command handles file write error."""
        mock_load.return_value = MagicMock()
        mock_export.return_value = "content"

        # Try to write to an invalid path
        result = runner.invoke(app, ["save", "/invalid/path/file.md"])

        # Should handle error gracefully
        assert result.exit_code != 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    def test_save_with_empty_content(self, mock_export, mock_load, tmp_path):
        """Test saving with empty content."""
        mock_load.return_value = MagicMock()
        mock_export.return_value = ""

        output_file = tmp_path / "empty.md"
        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text() == ""

    @patch("schema_report_cli.AssetRelationshipGraph")
    @patch("schema_report_cli.export_report")
    def test_save_creates_parent_directories(self, mock_export, mock_graph_class, tmp_path):
        """Test that save creates parent directories."""
        mock_graph_class.return_value = MagicMock()
        mock_export.return_value = "content"

        nested_path = tmp_path / "deeply" / "nested" / "path" / "report.md"
        result = runner.invoke(app, ["save", str(nested_path)])

        assert result.exit_code == 0
        assert nested_path.exists()
        assert nested_path.parent.exists()

    @patch("schema_report_cli.AssetRelationshipGraph")
    @patch("schema_report_cli.generate_markdown_report")
    def test_md_with_large_graph(self, mock_gen, mock_graph_class):
        """Test md command with large graph."""
        mock_graph = MagicMock()
        # Simulate large graph
        mock_graph.assets = {f"ASSET{i}": MagicMock() for i in range(1000)}
        mock_graph_class.return_value = mock_graph
        mock_gen.return_value = "# Large Report\n" + ("x" * 10000)

        result = runner.invoke(app, ["md"])

        assert result.exit_code == 0

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    def test_save_overwrites_existing_file(self, mock_export, mock_load, tmp_path):
        """Test that save overwrites existing file."""
        mock_load.return_value = MagicMock()
        mock_export.return_value = "new content"

        output_file = tmp_path / "existing.md"
        output_file.write_text("old content")

        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        assert output_file.read_text() == "new content"

    def test_invalid_command(self):
        """Test invoking invalid command."""
        result = runner.invoke(app, ["invalid"])

        assert result.exit_code != 0

    @patch("schema_report_cli.load_graph")
    @patch("schema_report_cli.export_report")
    def test_save_with_special_characters_in_path(self, mock_export, mock_load, tmp_path):
        """Test save with special characters in filename."""
        mock_load.return_value = MagicMock()
        mock_export.return_value = "content"

        # Test with spaces and special chars (where allowed by OS)
        output_file = tmp_path / "report with spaces.md"
        result = runner.invoke(app, ["save", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()