from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Mapping

import pytest


def _load_module_for_test(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    extra_env: Mapping[str, str] | None = None,
):
    """
    Prepare and import a fresh copy of the CLI module with environment and import path redirected to a temporary directory.
    
    Copies the repository CLI script into tmp_path, sets SCHEMA_REPORT_LOG to a file inside tmp_path, prepends tmp_path to sys.path, and imports (then reloads) the copied module so its top-level code runs under the patched environment.
    
    Parameters:
        monkeypatch (pytest.MonkeyPatch): Test fixture used to modify environment and sys.path.
        tmp_path (Path): Temporary directory where the CLI copy and log file will be placed.
        extra_env (Mapping[str, str] | None): Additional environment variables to apply (merged with the default SCHEMA_REPORT_LOG).
    
    Returns:
        module: The imported CLI module object corresponding to the copied script.
    """
    # Ensure env log path goes to tmp_path
    env: dict[str, str] = dict(extra_env or {})
    env.setdefault("SCHEMA_REPORT_LOG", str(tmp_path / "cli.log"))
    monkeypatch.setenv("SCHEMA_REPORT_LOG", env["SCHEMA_REPORT_LOG"])

    # Copy the real CLI script into tmp_path under a throwaway name
    cli_src = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "schema_report_cli.py"
    assert cli_src.exists(), f"CLI source not found: {cli_src}"

    cli_copy = tmp_path / "schema_report_cli_copy.py"
    cli_copy.write_text(cli_src.read_text(encoding="utf-8"), encoding="utf-8")

    # Import the copy so the module's top-level code runs with the patched env
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("schema_report_cli_copy")
    importlib.reload(module)
    return module


def test_invalid_format_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should exit with code 1 and print a message on invalid format."""
    mod = _load_module_for_test(monkeypatch, tmp_path)

    # Simulate CLI argv with invalid format
    monkeypatch.setattr(
        sys,
        "argv",
        ["schema_report_cli", "--fmt", "not-a-format"],
    )

    rc = mod.main()
    assert rc == 1

    captured = capsys.readouterr()
    # Our CLI prints "Error: Invalid output format. Please use one of: ..."
    assert "Invalid output format" in captured.err


def test_json_output_writes_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """--fmt json and --output should produce a JSON file with schema_report key."""
    mod = _load_module_for_test(monkeypatch, tmp_path)

    out_file = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["schema_report_cli", "--fmt", "json", "--output", str(out_file)],
    )

    rc = mod.main()
    assert rc == 0
    assert out_file.exists()

    text = out_file.read_text(encoding="utf-8")
    data = json.loads(text)
    # JSON produced by convert_markdown_to_json wraps markdown under "schema_report"
    assert "schema_report" in data


def test_generate_report_failure_does_not_leave_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    If report generation fails, CLI should not leave a partial output file.

    The user-facing error should stay generic and not expose internals.
    """
    mod = _load_module_for_test(monkeypatch, tmp_path)

    def fail_generate(graph):  # noqa: ARG001
        """
        Test helper that simulates a generation failure by always raising a RuntimeError.
        
        Parameters:
        	graph: Ignored. Present to match the signature of the real generator.
        
        Raises:
        	RuntimeError: Always raised with the message "boom".
        """
        raise RuntimeError("boom")

    # Patch the imported generate_schema_report inside the CLI module
    monkeypatch.setattr(mod, "generate_schema_report", fail_generate)

    out_file = tmp_path / "should_not_exist.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        ["schema_report_cli", "--fmt", "markdown", "--output", str(out_file)],
    )

    rc = mod.main()
    assert rc == 1

    # Ensure no partial file left on disk
    assert not out_file.exists()

    # User-facing message should be generic
    captured = capsys.readouterr()
    err_lower = captured.err.lower()
    assert "report generation failed" in err_lower or "unexpected error" in err_lower