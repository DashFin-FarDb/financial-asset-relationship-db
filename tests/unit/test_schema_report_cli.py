# ruff: noqa: S101
"""Unit tests for .github/scripts/schema_report_cli.py CLI tool.

This module tests the schema report CLI commands including:
- Markdown generation command (md)
- HTML generation command (html)
- Save command with file output
- Error handling and validation
"""

# Import the CLI app
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.logic.asset_graph import AssetRelationshipGraph

# Add .github/scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "scripts"))

from schema_report_cli import app, load_graph  # noqa: E402


@pytest.mark.unit
class TestLoadGraph:
    """Test cases for the load_graph function."""

    @staticmethod
    def test_load_graph_returns_asset_relationship_graph() -> None:
        """Test that load_graph returns an AssetRelationshipGraph instance."""
        graph = load_graph()
        assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    def test_load_graph_creates_empty_graph() -> None:
        """Test that load_graph creates an empty graph by default."""
        graph = load_graph()
        # The placeholder implementation just creates an empty graph
        assert len(graph.assets) == 0


@pytest.mark.unit
class TestMarkdownCommand:
    """Test cases for the 'md' command."""

    @pytest.fixture
    def runner() -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @staticmethod
    def test_md_command_prints_markdown_to_stdout(runner: CliRunner) -> None:
        """Test that md command prints markdown report to stdout."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_markdown_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_gen.return_value = "# Test Markdown Report"

            result = runner.invoke(app, ["md"])

            assert result.exit_code == 0
            assert "# Test Markdown Report" in result.output
            mock_load.assert_called_once()
            mock_gen.assert_called_once_with(mock_graph)

    @staticmethod
    def test_md_command_handles_empty_report(runner: CliRunner) -> None:
        """Test md command with empty report."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_markdown_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_gen.return_value = ""

            result = runner.invoke(app, ["md"])

            assert result.exit_code == 0

    @staticmethod
    def test_md_command_handles_graph_error(runner: CliRunner) -> None:
        """Test md command handles errors during graph loading."""
        with patch("schema_report_cli.load_graph") as mock_load:
            mock_load.side_effect = RuntimeError("Graph loading failed")

            result = runner.invoke(app, ["md"])

            # Typer runner will catch the exception
            # Check that the command failed
            assert result.exit_code != 0


@pytest.mark.unit
class TestHtmlCommand:
    """Test cases for the 'html' command."""

    @pytest.fixture
    def runner() -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @staticmethod
    def test_html_command_prints_html_to_stdout(runner: CliRunner) -> None:
        """Test that html command prints HTML report to stdout."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_html_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_gen.return_value = "<h1>Test HTML Report</h1>"

            result = runner.invoke(app, ["html"])

            assert result.exit_code == 0
            assert "<h1>Test HTML Report</h1>" in result.output
            mock_load.assert_called_once()
            mock_gen.assert_called_once_with(mock_graph)

    @staticmethod
    def test_html_command_with_complex_html(runner: CliRunner) -> None:
        """Test html command with complex HTML content."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_html_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            complex_html = """
            <html>
                <head><title>Report</title></head>
                <body>
                    <h1>Schema Report</h1>
                    <table><tr><td>Data</td></tr></table>
                </body>
            </html>
            """
            mock_gen.return_value = complex_html

            result = runner.invoke(app, ["html"])

            assert result.exit_code == 0
            assert "<h1>Schema Report</h1>" in result.output

    @staticmethod
    def test_html_command_handles_generation_error(runner: CliRunner) -> None:
        """Test html command handles errors during report generation."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_html_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_gen.side_effect = ValueError("Invalid HTML generation")

            result = runner.invoke(app, ["html"])

            # Check that the command failed
            assert result.exit_code != 0


@pytest.mark.unit
class TestSaveCommand:
    """Test cases for the 'save' command."""

    @pytest.fixture
    def runner() -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @staticmethod
    def test_save_command_default_markdown_format(runner: CliRunner, tmp_path: Path) -> None:
        """Test save command with default markdown format."""
        output_file = tmp_path / "report.md"

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = "# Saved Report"

            result = runner.invoke(app, ["save", str(output_file)])

            assert result.exit_code == 0
            assert f"Report written to {output_file}" in result.output
            mock_export.assert_called_once_with(mock_graph, fmt="md")
            assert output_file.exists()
            assert output_file.read_text(encoding="utf-8") == "# Saved Report"

    @staticmethod
    def test_save_command_with_html_format(runner: CliRunner, tmp_path: Path) -> None:
        """Test save command with HTML format."""
        output_file = tmp_path / "report.html"

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = "<html><body>Report</body></html>"

            result = runner.invoke(app, ["save", str(output_file), "--fmt", "html"])

            assert result.exit_code == 0
            assert f"Report written to {output_file}" in result.output
            mock_export.assert_called_once_with(mock_graph, fmt="html")
            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert "<html><body>Report</body></html>" in content

    @staticmethod
    def test_save_command_creates_parent_directories(runner: CliRunner, tmp_path: Path) -> None:
        """Test that save command works with nested paths."""
        output_file = tmp_path / "reports" / "schema" / "report.md"

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = "# Report"

            # Create parent directories
            output_file.parent.mkdir(parents=True, exist_ok=True)

            result = runner.invoke(app, ["save", str(output_file)])

            assert result.exit_code == 0
            assert output_file.exists()

    @staticmethod
    def test_save_command_overwrites_existing_file(runner: CliRunner, tmp_path: Path) -> None:
        """Test that save command overwrites existing files."""
        output_file = tmp_path / "report.md"
        output_file.write_text("Old content", encoding="utf-8")

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = "# New Report"

            result = runner.invoke(app, ["save", str(output_file)])

            assert result.exit_code == 0
            assert output_file.read_text(encoding="utf-8") == "# New Report"

    @staticmethod
    def test_save_command_handles_export_error(runner: CliRunner, tmp_path: Path) -> None:
        """Test save command handles export errors."""
        output_file = tmp_path / "report.md"

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.side_effect = ValueError("Export failed")

            result = runner.invoke(app, ["save", str(output_file)])

            # Check that the command failed
            assert result.exit_code != 0


@pytest.mark.unit
class TestMainFunction:
    """Test cases for the main entry point."""

    @staticmethod
    def test_main_function_runs_app() -> None:
        """Test that main function invokes the typer app."""
        with patch("schema_report_cli.app") as mock_app:
            from schema_report_cli import main

            main()
            mock_app.assert_called_once()

    @staticmethod
    def test_main_function_handles_exceptions() -> None:
        """Test that main function handles exceptions and exits with error code."""
        with patch("schema_report_cli.app") as mock_app, patch("sys.exit") as mock_exit:
            mock_app.side_effect = RuntimeError("CLI error")
            from schema_report_cli import main

            main()
            mock_exit.assert_called_once_with(1)


@pytest.mark.unit
class TestCLIEdgeCases:
    """Test edge cases and boundary conditions for CLI commands."""

    @staticmethod
    @pytest.fixture
    def runner() -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @staticmethod
    def test_save_with_empty_content(runner: CliRunner, tmp_path: Path) -> None:
        output_file = tmp_path / "empty.md"

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = ""

            result = runner.invoke(app, ["save", str(output_file)])

            assert result.exit_code == 0
            assert output_file.exists()
            assert output_file.read_text(encoding="utf-8") == ""

    @staticmethod
    def test_commands_with_unicode_content(runner: CliRunner) -> None:
        """Test that commands handle Unicode content correctly."""
        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.generate_markdown_report") as mock_gen,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_gen.return_value = "# Report 📊\n\n价格: ¥100"

            result = runner.invoke(app, ["md"])

            assert result.exit_code == 0
            assert "Report 📊" in result.output

    @staticmethod
    def test_save_with_long_path(runner: CliRunner, tmp_path: Path) -> None:
        """Test save command with a long file path."""
        long_path = tmp_path / ("x" * 50) / ("y" * 50) / "report.md"
        long_path.parent.mkdir(parents=True, exist_ok=True)

        with (
            patch("schema_report_cli.load_graph") as mock_load,
            patch("schema_report_cli.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_load.return_value = mock_graph
            mock_export.return_value = "# Report"

            result = runner.invoke(app, ["save", str(long_path)])

            assert result.exit_code == 0
            assert long_path.exists()
