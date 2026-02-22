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
    """
    Get the filesystem path to the repository's schema_report_cli.py script.

    Returns:
        Path: Path pointing to .github/scripts/schema_report_cli.py located under the repository root.
    """
    return _repo_root() / ".github" / "scripts" / "schema_report_cli.py"


def _load_cli_module_for_unit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> ModuleType:
    """
    Load the CLI script from its on-disk location and return it as an imported module.

    Sets the SCHEMA_REPORT_LOG environment variable to a log file under tmp_path to prevent test logging from touching the repository tree.

    Parameters:
        monkeypatch (pytest.MonkeyPatch): pytest monkeypatch fixture used to modify environment variables.
        tmp_path (Path): Temporary directory in which the redirected log file will be created.

    Returns:
        module (ModuleType): The imported CLI module.
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
    """
    Provide a freshly loaded CLI module for unit tests.

    Returns:
        cli_module (ModuleType): The loaded CLI module object.
    """
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
            """
            Simulate a failing Path.replace by always raising a RuntimeError.

            Raises:
                RuntimeError: with message "simulated replace failure".
            """
            raise RuntimeError("simulated replace failure")

        monkeypatch.setattr(_Path, "replace", failing_replace, raising=True)

        with pytest.raises(RuntimeError, match="simulated replace failure"):
            cli_module.write_atomic(target, "content")

        # Target should not exist and no extra temp files should remain.
        assert not target.exists()
        final_entries = set(tmp_path.iterdir())
        assert final_entries == initial_entries
