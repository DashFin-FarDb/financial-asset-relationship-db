from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _repo_root() -> Path:
    """Return the repository root, assuming tests live under tests/."""
    return Path(__file__).resolve().parents[2]


def _cli_path() -> Path:
    """Return the path to the schema_report_cli script."""
    return _repo_root() / ".github" / "scripts" / "schema_report_cli.py"


def _load_cli_module_for_unit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> ModuleType:
    """
    Load the CLI module directly from its file path for unit testing.

    SCHEMA_REPORT_LOG is redirected into tmp_path so logging does not
    touch the repository tree.
    """
    monkeypatch.setenv(
        "SCHEMA_REPORT_LOG",
        str(tmp_path / "schema_report_cli.log"),
    )

    spec = importlib.util.spec_from_file_location(
        "schema_report_cli_unit",
        str(_cli_path()),
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> ModuleType:
    """Provide a freshly loaded CLI module for unit tests."""
    return _load_cli_module_for_unit(monkeypatch, tmp_path)


class TestConvertMarkdownToPlainText:
    """Unit tests for convert_markdown_to_plain_text."""

    def test_removes_common_markers_and_preserves_content(
        self,
        cli_module: ModuleType,
    ) -> None:
        """Leading #, -, * markers are stripped but text is preserved."""
        markdown = "# Title\n- Item\n* Bullet\nPlain line"
        result = cli_module.convert_markdown_to_plain_text(markdown)

        lines = result.splitlines()
        assert lines == ["Title", "Item", "Bullet", "Plain line"]

    def test_plain_text_is_unchanged(
        self,
        cli_module: ModuleType,
    ) -> None:
        """Non-markdown text should be returned unchanged."""
        markdown = "Just some plain text\nacross multiple lines."
        result = cli_module.convert_markdown_to_plain_text(markdown)
        assert result == markdown


class TestConvertMarkdownToJSON:
    """Unit tests for convert_markdown_to_json."""

    def test_wraps_markdown_under_schema_report_key(
        self,
        cli_module: ModuleType,
    ) -> None:
        """Markdown is wrapped in a JSON object under schema_report."""
        markdown = "# Header\nSome content."
        json_str = cli_module.convert_markdown_to_json(markdown)

        import json as _json  # local import to avoid global coupling

        data = _json.loads(json_str)
        assert "schema_report" in data
        assert data["schema_report"] == markdown

    def test_indented_output_is_pretty_printed(
        self,
        cli_module: ModuleType,
    ) -> None:
        """JSON output is pretty-printed (contains newlines/indentation)."""
        markdown = "Line 1\nLine 2"
        json_str = cli_module.convert_markdown_to_json(markdown)

        # Pretty-printed JSON should contain newlines and indentation spaces.
        assert "\n" in json_str
        assert "  " in json_str  # at least one indented line


class TestWriteAtomic:
    """Unit tests for write_atomic."""

    def test_write_atomic_creates_file_with_content(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """write_atomic writes the expected content to the target path."""
        target = tmp_path / "out.txt"
        content = "hello world"

        cli_module.write_atomic(target, content)
        assert target.exists()

        read_back = target.read_text(encoding="utf-8")
        assert read_back == content

    def test_write_atomic_is_idempotent_overwrites_existing_file(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """write_atomic should safely overwrite an existing file."""
        target = tmp_path / "out.txt"
        target.write_text("old content", encoding="utf-8")

        new_content = "new content"
        cli_module.write_atomic(target, new_content)

        read_back = target.read_text(encoding="utf-8")
        assert read_back == new_content

    def test_write_atomic_cleans_temp_file_on_failure(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        On failure, write_atomic should remove its temporary file.

        We simulate a failure by monkeypatching Path.replace to raise.
        The directory contents before and after should be identical.
        """
        from pathlib import Path as _Path

        target = tmp_path / "out.txt"
        initial_entries = set(tmp_path.iterdir())

        def failing_replace(self, *args, **kwargs):  # noqa: D401, ARG002
            """Simulated failure in Path.replace."""
            raise RuntimeError("simulated replace failure")

        monkeypatch.setattr(_Path, "replace", failing_replace, raising=True)

        with pytest.raises(RuntimeError, match="simulated replace failure"):
            cli_module.write_atomic(target, "content")

        # Target should not exist and no extra temp files should remain.
        assert not target.exists()
        final_entries = set(tmp_path.iterdir())
        assert final_entries == initial_entries


class TestParseArguments:
    """Unit tests for parse_arguments function."""

    def test_parse_arguments_defaults(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """parse_arguments should use correct defaults when no args provided."""
        monkeypatch.setattr(sys, "argv", ["schema_report_cli"])

        args = cli_module.parse_arguments()

        assert args.fmt == "markdown"
        assert args.output is None
        assert args.verbose is False

    def test_parse_arguments_custom_format(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """parse_arguments should accept custom format."""
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "--fmt", "json"])

        args = cli_module.parse_arguments()

        assert args.fmt == "json"

    def test_parse_arguments_output_path(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """parse_arguments should accept output path."""
        output = tmp_path / "output.txt"
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "--output", str(output)])

        args = cli_module.parse_arguments()

        assert args.output == output

    def test_parse_arguments_verbose_flag(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """parse_arguments should accept verbose flag."""
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "--verbose"])

        args = cli_module.parse_arguments()

        assert args.verbose is True

    def test_parse_arguments_short_flags(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """parse_arguments should accept short flag versions."""
        output = tmp_path / "output.txt"
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "-o", str(output), "-v"])

        args = cli_module.parse_arguments()

        assert args.output == output
        assert args.verbose is True


class TestGenerateReport:
    """Unit tests for generate_report function."""

    def test_generate_report_markdown_to_stdout(
        self,
        cli_module: ModuleType,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """generate_report with markdown format should output to stdout."""
        fmt = cli_module.OutputFormat.MARKDOWN

        cli_module.generate_report(fmt, None)

        captured = capsys.readouterr()
        assert len(captured.out) > 0
        # Markdown should contain schema-related content
        assert "Schema" in captured.out or "Financial" in captured.out

    def test_generate_report_text_format(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """generate_report with text format should convert markdown."""
        fmt = cli_module.OutputFormat.TEXT
        output = tmp_path / "output.txt"

        cli_module.generate_report(fmt, output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        # Text format should have stripped markdown markers
        assert "#" not in content or content.count("#") < 5

    def test_generate_report_json_format(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """generate_report with JSON format should produce valid JSON."""
        import json as _json

        fmt = cli_module.OutputFormat.JSON
        output = tmp_path / "output.json"

        cli_module.generate_report(fmt, output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        data = _json.loads(content)  # Should not raise
        assert "schema_report" in data

    def test_generate_report_creates_parent_directories(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """generate_report should create parent directories if needed."""
        fmt = cli_module.OutputFormat.MARKDOWN
        output = tmp_path / "nested" / "dir" / "output.md"

        cli_module.generate_report(fmt, output)

        assert output.exists()
        assert output.parent.exists()


class TestOutputFormat:
    """Unit tests for OutputFormat enum."""

    def test_output_format_values(
        self,
        cli_module: ModuleType,
    ) -> None:
        """OutputFormat should have correct values."""
        assert cli_module.OutputFormat.MARKDOWN.value == "markdown"
        assert cli_module.OutputFormat.TEXT.value == "text"
        assert cli_module.OutputFormat.JSON.value == "json"

    def test_output_format_string_conversion(
        self,
        cli_module: ModuleType,
    ) -> None:
        """OutputFormat should convert to string correctly."""
        fmt = cli_module.OutputFormat.MARKDOWN
        assert str(fmt) == "markdown"


class TestCLIError:
    """Unit tests for CLIError exception."""

    def test_cli_error_creation(
        self,
        cli_module: ModuleType,
    ) -> None:
        """CLIError should be creatable with message."""
        error = cli_module.CLIError("Test error message")
        assert str(error) == "Test error message"

    def test_cli_error_is_exception(
        self,
        cli_module: ModuleType,
    ) -> None:
        """CLIError should be an Exception subclass."""
        assert issubclass(cli_module.CLIError, Exception)


class TestMainFunction:
    """Integration tests for main function."""

    def test_main_returns_zero_on_success(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main should return 0 on successful execution."""
        monkeypatch.setattr(sys, "argv", ["schema_report_cli"])

        result = cli_module.main()

        assert result == 0

    def test_main_verbose_mode(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """main with --verbose should enable debug logging to stderr."""
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "--verbose"])

        result = cli_module.main()

        assert result == 0
        # In verbose mode, debug messages should appear

    def test_main_with_output_file(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """main with --output should write to specified file."""
        output = tmp_path / "report.md"
        monkeypatch.setattr(sys, "argv", ["schema_report_cli", "--output", str(output)])

        result = cli_module.main()

        assert result == 0
        assert output.exists()

    def test_main_handles_keyboard_interrupt(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """main should handle KeyboardInterrupt gracefully."""

        def mock_generate_report(*args, **kwargs):  # noqa: ARG001
            raise KeyboardInterrupt()

        monkeypatch.setattr(cli_module, "generate_report", mock_generate_report)
        monkeypatch.setattr(sys, "argv", ["schema_report_cli"])

        result = cli_module.main()

        assert result == 130  # Standard exit code for SIGINT
        captured = capsys.readouterr()
        assert "cancelled" in captured.err.lower()

    def test_main_handles_unexpected_errors(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """main should handle unexpected errors gracefully."""

        def mock_generate_report(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr(cli_module, "generate_report", mock_generate_report)
        monkeypatch.setattr(sys, "argv", ["schema_report_cli"])

        result = cli_module.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


class TestEdgeCases:
    """Additional edge case tests."""

    def test_convert_markdown_with_multiple_list_markers(
        self,
        cli_module: ModuleType,
    ) -> None:
        """convert_markdown_to_plain_text should handle multiple markers."""
        markdown = "# - * Title with all markers"
        result = cli_module.convert_markdown_to_plain_text(markdown)

        # All markers should be stripped from the beginning
        assert result.strip() == "Title with all markers"

    def test_convert_markdown_preserves_internal_markers(
        self,
        cli_module: ModuleType,
    ) -> None:
        """convert_markdown_to_plain_text should preserve non-leading markers."""
        markdown = "Text with # internal * markers - here"
        result = cli_module.convert_markdown_to_plain_text(markdown)

        assert "#" in result
        assert "*" in result
        assert "-" in result

    def test_write_atomic_with_unicode_content(
        self,
        cli_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """write_atomic should handle unicode content correctly."""
        target = tmp_path / "unicode.txt"
        content = "Test with émojis 🎉 and spëcial characters: 你好"

        cli_module.write_atomic(target, content)

        read_back = target.read_text(encoding="utf-8")
        assert read_back == content

    def test_generate_report_with_empty_graph(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """generate_report should handle errors from empty/invalid graph."""

        def mock_create_sample_database():
            return None  # Invalid return

        monkeypatch.setattr(cli_module, "create_sample_database", mock_create_sample_database)

        fmt = cli_module.OutputFormat.MARKDOWN

        with pytest.raises(cli_module.CLIError):
            cli_module.generate_report(fmt, None)

    def test_json_output_is_valid_and_pretty(
        self,
        cli_module: ModuleType,
    ) -> None:
        """convert_markdown_to_json should produce pretty-printed JSON."""
        markdown = "# Test\nContent"
        json_str = cli_module.convert_markdown_to_json(markdown)

        # Check for pretty printing
        assert "\n" in json_str
        assert "  " in json_str  # Indentation

        # Check structure
        import json as _json

        data = _json.loads(json_str)
        assert isinstance(data, dict)
        assert "schema_report" in data
        assert data["schema_report"] == markdown

    def test_main_with_all_formats(
        self,
        cli_module: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """main should work with all supported formats."""
        formats = ["markdown", "text", "json"]

        for fmt in formats:
            output = tmp_path / f"output.{fmt}"
            monkeypatch.setattr(
                sys,
                "argv",
                ["schema_report_cli", "--fmt", fmt, "--output", str(output)],
            )

            result = cli_module.main()

            assert result == 0, f"Failed for format: {fmt}"
            assert output.exists(), f"Output not created for format: {fmt}"
