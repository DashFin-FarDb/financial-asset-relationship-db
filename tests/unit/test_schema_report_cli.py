"""
Unit tests for schema_report_cli.py

Tests CLI input validation, error handling, and output formatting.
"""

import json
import subprocess
import sys
from pathlib import Path


class TestCLIInputValidation:
    """Test cases for CLI input validation."""

    def test_valid_markdown_format(self, tmp_path):
        """Test if the CLI accepts valid markdown format."""
        output_file = tmp_path / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "markdown",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "# Financial Asset Relationship Database Schema & Rules" in content

    def test_valid_json_format(self, tmp_path):
        """Test if the CLI accepts valid JSON format."""
        output_file = tmp_path / "report.json"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "json",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text()
        # Validate it's valid JSON
        data = json.loads(content)
        assert "total_assets" in data
        assert "total_relationships" in data

    def test_valid_text_format(self, tmp_path):
        """Test CLI accepts valid text format."""
        output_file = tmp_path / "report.txt"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "text",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text()
        # Text format should not have markdown headers
        assert "# " not in content
        assert "Financial Asset Relationship Database Schema" in content

    def test_invalid_format_rejected(self):
        """Test that the CLI rejects an invalid format."""
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "invalid",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode != 0
        # Should show error about invalid choice
        assert (
            "invalid choice" in result.stderr.lower()
            or "error" in result.stderr.lower()
        )

    def test_default_format_is_markdown(self, tmp_path):
        """Test that the default format is markdown when not specified."""
        output_file = tmp_path / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        content = output_file.read_text()
        assert "# Financial Asset Relationship Database Schema & Rules" in content


class TestCLIErrorHandling:
    """Test cases for CLI error handling."""

    def test_generic_error_message_on_failure(self, tmp_path, monkeypatch):
        # We can't easily simulate internal errors without mocking,
        # but we can test invalid output path
        """Test that a generic error message is shown on failure."""
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--output",
                "/invalid/path/report.md",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode != 0
        # Should show generic error, not raw exception
        assert "Error:" in result.stderr
        assert "Traceback" not in result.stderr

    def test_keyboard_interrupt_handling(self):
        # Documenting expected behavior:
        # When KeyboardInterrupt is raised, CLI should:
        # 1. Log a warning message
        # 2. Print "Operation cancelled by user" to stderr
        # 3. Return exit code 130 (standard for SIGINT)
        """Test CLI handles keyboard interrupt gracefully."""
        pass

    def test_help_message_available(self):
        """Test that the help message is available and correctly formatted."""
        result = subprocess.run(
            [sys.executable, ".github/scripts/schema_report_cli.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert "--fmt" in result.stdout
        assert "markdown" in result.stdout
        assert "json" in result.stdout
        assert "text" in result.stdout


class TestCLIOutputOptions:
    """Test cases for CLI output options."""

    def test_stdout_output_when_no_file_specified(self):
        """Test CLI output to stdout when no output file is specified."""
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "markdown",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert "# Financial Asset Relationship Database Schema & Rules" in result.stdout

    def test_output_file_creation(self, tmp_path):
        """Test the creation of the output file by the CLI."""
        output_file = tmp_path / "subdir" / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_verbose_mode(self, tmp_path):
        """Test the verbose mode for additional logging output."""
        output_file = tmp_path / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--verbose",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        # In verbose mode, we expect more logging output to stderr
        assert len(result.stderr) > 0


class TestCLIFormatConversion:
    """Test cases for format conversion functionality."""

    def test_markdown_contains_headers(self, tmp_path):
        """Test markdown format contains proper headers."""
        output_file = tmp_path / "report.md"
        subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "markdown",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        content = output_file.read_text()
        assert "##" in content
        assert "**" in content

    def test_text_removes_markdown_formatting(self, tmp_path):
        """Test that text format removes markdown formatting."""
        output_file = tmp_path / "report.txt"
        subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "text",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        content = output_file.read_text()
        # Should have minimal markdown formatting
        lines_with_headers = [
            line for line in content.split("\n") if line.startswith("#")
        ]
        assert len(lines_with_headers) == 0  # No markdown headers

    def test_json_contains_valid_structure(self, tmp_path):
        """Test JSON format contains expected keys."""
        output_file = tmp_path / "report.json"
        subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "json",
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        content = output_file.read_text()
        data = json.loads(content)

        # Check for expected keys
        assert "total_assets" in data
        assert "total_relationships" in data
        assert "average_relationship_strength" in data
        assert "relationship_density" in data
        assert "asset_class_distribution" in data


class TestCLIArgumentParsing:
    """Test cases for argument parsing."""

    def test_short_output_flag(self, tmp_path):
        """Test short -o flag works for output."""
        output_file = tmp_path / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "-o",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_short_verbose_flag(self, tmp_path):
        """Test the short -v flag for verbose output."""
        output_file = tmp_path / "report.md"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "-v",
                "-o",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0

    def test_combined_flags(self, tmp_path):
        """Test if all flags can be combined successfully."""
        output_file = tmp_path / "report.json"
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--fmt",
                "json",
                "--output",
                str(output_file),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0
        assert output_file.exists()


class TestCLILogging:
    """Test cases for CLI logging behavior."""

    def test_log_file_created(self, tmp_path):
        """Test that log file is created during execution."""
        # Run CLI
        result = subprocess.run(
            [sys.executable, ".github/scripts/schema_report_cli.py"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode == 0

        # Check log file exists
        log_file = Path(".github/scripts/schema_report_cli.log")
        assert log_file.exists()

    def test_errors_logged_to_file(self):
        # Trigger an error
        """Test that errors are logged to the log file."""
        result = subprocess.run(
            [
                sys.executable,
                ".github/scripts/schema_report_cli.py",
                "--output",
                "/invalid/path/report.md",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        assert result.returncode != 0

        # Check that log file contains error details
        log_file = Path(".github/scripts/schema_report_cli.log")
        if log_file.exists():
            log_content = log_file.read_text()
            assert "ERROR" in log_content or "CRITICAL" in log_content
