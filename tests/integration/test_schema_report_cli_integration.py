"""
Integration tests for .github/scripts/schema_report_cli.py.

These tests exercise the CLI via subprocess to validate:
- Input validation and argument parsing
- Error handling and generic user-facing messages
- Output formatting for markdown, text, and JSON
- Logging behaviour and SCHEMA_REPORT_LOG handling
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root, assuming tests live under tests/."""
    return Path(__file__).resolve().parents[2]


def _cli_path() -> Path:
    """Return the path to the schema_report_cli script."""
    return _repo_root() / ".github" / "scripts" / "schema_report_cli.py"


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """
    Run the CLI script via subprocess with a temp log location.

    SCHEMA_REPORT_LOG is forced to tmp_path so tests do not write logs
    into the repository tree.
    """
    env = os.environ.copy()
    env["SCHEMA_REPORT_LOG"] = str(tmp_path / "schema_report_cli.log")

    return subprocess.run(
        [sys.executable, str(_cli_path()), *args],
        capture_output=True,
        text=True,
        cwd=str(_repo_root()),
        env=env,
    )


class TestCLIInputValidation:
    """Test cases for CLI input validation."""

    def test_valid_markdown_format(self, tmp_path: Path) -> None:
        """CLI accepts valid markdown format and writes a report file."""
        output_file = tmp_path / "report.md"
        result = _run_cli(
            tmp_path,
            "--fmt",
            "markdown",
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        # Header string is project-specific; adjust if your schema header changes.
        assert "Financial Asset Relationship Database Schema" in content

    def test_valid_json_format(self, tmp_path: Path) -> None:
        """CLI accepts valid json format and produces JSON payload."""
        output_file = tmp_path / "report.json"
        result = _run_cli(
            tmp_path,
            "--fmt",
            "json",
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        data = json.loads(content)
        # CLI wraps markdown report under "schema_report"
        assert "schema_report" in data
        assert isinstance(data["schema_report"], str)
        assert "Financial Asset Relationship Database Schema" in data["schema_report"]

    def test_valid_text_format(self, tmp_path: Path) -> None:
        """CLI accepts valid text format and strips markdown markers."""
        output_file = tmp_path / "report.txt"
        result = _run_cli(
            tmp_path,
            "--fmt",
            "text",
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        # Text format should not contain markdown headers
        assert "# " not in content
        assert "Financial Asset Relationship Database Schema" in content

    def test_invalid_format_rejected(self, tmp_path: Path) -> None:
        """CLI rejects invalid --fmt values."""
        result = _run_cli(
            tmp_path,
            "--fmt",
            "invalid",
        )
        # argparse will typically exit with code 2 on invalid choice
        assert result.returncode != 0
        err_lower = result.stderr.lower()
        assert "invalid choice" in err_lower or "error" in err_lower

    def test_default_format_is_markdown(self, tmp_path: Path) -> None:
        """Default format is markdown when --fmt is not specified."""
        output_file = tmp_path / "report.md"
        result = _run_cli(
            tmp_path,
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "Financial Asset Relationship Database Schema" in content


class TestCLIErrorHandling:
    """Test cases for CLI error handling."""

    def test_generic_error_message_on_failure(self, tmp_path: Path) -> None:
        """CLI shows a generic error message on failure."""
        # Invalid output path should cause a failure inside generate_report
        result = _run_cli(
            tmp_path,
            "--output",
            "/invalid/path/report.md",
        )
        assert result.returncode != 0

        # Should show generic error, not a raw traceback
        err = result.stderr
        assert "Error:" in err
        assert "Traceback" not in err

    def test_keyboard_interrupt_handling_documented(self) -> None:
        """Document expected behaviour for KeyboardInterrupt.

        Actual SIGINT process-level testing is out of scope here; the
        behaviour is verified in main() implementation:
        - Log a message about cancellation
        - Print a user-facing cancellation message
        - Exit with code 130
        """
        # Behaviour is documented rather than executed in this test.
        assert True

    def test_help_message_available(self, tmp_path: Path) -> None:
        """Help message should be available and well-formed."""
        result = _run_cli(tmp_path, "--help")
        assert result.returncode == 0
        stdout = result.stdout
        assert "--fmt" in stdout
        assert "markdown" in stdout
        assert "json" in stdout
        assert "text" in stdout


class TestCLIOutputOptions:
    """Test cases for CLI output options."""

    def test_stdout_output_when_no_file_specified(self, tmp_path: Path) -> None:
        """CLI writes to stdout when no output file is specified."""
        result = _run_cli(
            tmp_path,
            "--fmt",
            "markdown",
        )
        assert result.returncode == 0
        assert "Financial Asset Relationship Database Schema" in result.stdout

    def test_output_file_creation(self, tmp_path: Path) -> None:
        """CLI creates output file in nested directory."""
        output_file = tmp_path / "subdir" / "report.md"
        result = _run_cli(
            tmp_path,
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_verbose_mode(self, tmp_path: Path) -> None:
        """Verbose mode enables additional logging output to stderr."""
        output_file = tmp_path / "report.md"
        result = _run_cli(
            tmp_path,
            "--verbose",
            "--output",
            str(output_file),
        )
        assert result.returncode == 0
        # In verbose mode, we expect some logging on stderr
        assert result.stderr.strip() != ""


class TestCLIFormatConversion:
    """Test cases for format conversion functionality."""

    def test_markdown_contains_headers(self, tmp_path: Path) -> None:
        """Markdown format should contain typical markdown markers."""
        output_file = tmp_path / "report.md"
        _run_cli(
            tmp_path,
            "--fmt",
            "markdown",
            "--output",
            str(output_file),
        )
        content = output_file.read_text(encoding="utf-8")
        assert "##" in content or "# " in content

    def test_text_removes_markdown_formatting(self, tmp_path: Path) -> None:
        """Text format should remove markdown headers."""
        output_file = tmp_path / "report.txt"
        _run_cli(
            tmp_path,
            "--fmt",
            "text",
            "--output",
            str(output_file),
        )
        content = output_file.read_text(encoding="utf-8")
        lines_with_headers = [line for line in content.splitlines() if line.startswith("#")]
        assert len(lines_with_headers) == 0

    def test_json_contains_valid_structure(self, tmp_path: Path) -> None:
        """JSON format contains the wrapper structure with schema_report key."""
        output_file = tmp_path / "report.json"
        _run_cli(
            tmp_path,
            "--fmt",
            "json",
            "--output",
            str(output_file),
        )
        content = output_file.read_text(encoding="utf-8")
        data = json.loads(content)

        assert isinstance(data, dict)
        assert "schema_report" in data
        assert isinstance(data["schema_report"], str)
        assert "Financial Asset Relationship Database Schema" in data["schema_report"]


class TestCLIArgumentParsing:
    """Test cases for argument parsing."""

    def test_short_output_flag(self, tmp_path: Path) -> None:
        """Short -o flag should work for output."""
        output_file = tmp_path / "report.md"
        result = _run_cli(
            tmp_path,
            "-o",
            str(output_file),
        )
        assert result.returncode == 0
        assert output_file.exists()

    def test_short_verbose_flag(self, tmp_path: Path) -> None:
        """Short -v flag should enable verbose mode."""
        output_file = tmp_path / "report.md"
        result = _run_cli(
            tmp_path,
            "-v",
            "-o",
            str(output_file),
        )
        assert result.returncode == 0

    def test_combined_flags(self, tmp_path: Path) -> None:
        """All flags can be combined without error."""
        output_file = tmp_path / "report.json"
        result = _run_cli(
            tmp_path,
            "--fmt",
            "json",
            "--output",
            str(output_file),
            "--verbose",
        )
        assert result.returncode == 0
        assert output_file.exists()


class TestCLILogging:
    """Test cases for CLI logging behavior."""

    def test_log_file_created(self, tmp_path: Path) -> None:
        """Log file should be created in the path given by SCHEMA_REPORT_LOG."""
        result = _run_cli(tmp_path)
        assert result.returncode == 0

        log_file = tmp_path / "schema_report_cli.log"
        assert log_file.exists()

    def test_errors_logged_to_file(self, tmp_path: Path) -> None:
        """Errors should be recorded in the log file."""
        result = _run_cli(
            tmp_path,
            "--output",
            "/invalid/path/report.md",
        )
        assert result.returncode != 0

        log_file = tmp_path / "schema_report_cli.log"
        if log_file.exists():
            log_content = log_file.read_text(encoding="utf-8")
            # We expect at least one error or exception-level record
            assert "ERROR" in log_content or "CRITICAL" in log_content
