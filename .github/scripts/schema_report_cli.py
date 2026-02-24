#!/usr/bin/env python3
"""
Schema Report CLI - generate financial asset relationship schema reports.

This CLI tool generates schema reports with validated input options and
proper error handling. User-facing errors stay generic while logs contain
detailed diagnostics.
"""

from __future__ import annotations

import argparse
import enum
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Import path bootstrapping
# ---------------------------------------------------------------------------


def _find_project_root(start: Path) -> Path:
    """
    Resolve the project root directory for running this script directly.

    The function walks up from `start` looking for a directory containing
    either `pyproject.toml` or a `src/` package directory.

    Args:
        start: Starting path, typically this file path.

    Returns:
        The resolved project root path.

    Raises:
        RuntimeError: If no suitable root directory can be found.
    """
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").exists() or (parent / "src").is_dir():
            return parent

    # Fallback to the current working directory for environments where the
    # script is copied or relocated (e.g., tests) but the project root is
    # still the CWD.
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() or (cwd / "src").is_dir():
        return cwd

    # If no project root could be determined, fail explicitly rather than
    # returning None implicitly. This matches the documented contract.
    raise RuntimeError(
        f"Could not determine project root starting from {start} or current working directory {cwd}"
    )


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.sample_data import create_sample_database  # noqa: E402
from src.reports.schema_report import generate_schema_report  # noqa: E402

# ---------------------------------------------------------------------------
# CLI types and errors
# ---------------------------------------------------------------------------


class OutputFormat(enum.Enum):
    """Constrained enum for valid output formats."""

    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"

    def __str__(self) -> str:
        return str(self.value)


class CLIError(Exception):
    """Base exception for CLI errors with user-friendly messages."""


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


def _resolve_log_path() -> Path:
    """
    Resolve the log file path.

    Order of preference:
    1) SCHEMA_REPORT_LOG env var
    2) Script directory (if writable)
    3) System temporary directory

    Returns:
        Path to the log file.
    """
    env_log = os.getenv("SCHEMA_REPORT_LOG")
    if env_log:
        return Path(env_log)

    default_log_path = Path(__file__).resolve().parent / "schema_report_cli.log"
    try:
        default_log_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = default_log_path.parent / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return default_log_path
    except Exception:
        return Path(tempfile.gettempdir()) / "schema_report_cli.log"


def configure_logging(verbose: bool) -> logging.Logger:
    """
    Configure CLI logging (file + stderr) in an idempotent way.

    File logs always include DEBUG. Stderr logs are WARNING by default and
    DEBUG when --verbose is set.

    Args:
        verbose: Whether to emit verbose diagnostics to stderr.

    Returns:
        A configured logger for this module.
    """
    log_path = _resolve_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_path = Path(tempfile.gettempdir()) / "schema_report_cli.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # keep file logs detailed
    logger.propagate = False

    # Avoid duplicate handlers if imported or invoked multiple times.
    if logger.handlers:
        # Update existing stream handler levels based on verbosity.
        for h in logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                h.setLevel(logging.DEBUG if verbose else logging.WARNING)
        return logger

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    stream_formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(stream_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _as_output_format(value: str) -> OutputFormat:
    """Parse --fmt into OutputFormat and raise argparse-friendly errors."""
    try:
        return OutputFormat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Invalid output format. Use one of: markdown, text, json."
        ) from exc


def parse_arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments for the Schema Report CLI.

    Recognizes:
    - --fmt: output format, one of 'markdown', 'text', or 'json'
      (default: 'markdown').
    - --output / -o: optional filesystem path to write the report;
      if omitted, stdout is used.
    - --verbose / -v: enable verbose logging to stderr.

    Args:
        argv: Optional argument list (defaults to sys.argv parsing).

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate schema reports for financial asset relationships.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fmt",
        type=_as_output_format,
        default=OutputFormat.MARKDOWN,
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: stdout).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MD_LINE_PREFIX = re.compile(r"^(?:[#]+\s*|[-*]\s+)")


def convert_markdown_to_plain_text(markdown: str) -> str:
    """
    Produce a plain-text version of a Markdown string.

    The conversion removes common leading Markdown markers from each line:
    heading hashes ('#') and list markers ('-' or '*'). Original line breaks
    are preserved.

    Args:
        markdown: Input Markdown text.

    Returns:
        Plain-text string with leading Markdown markers removed.
    """
    lines: list[str] = []
    for line in markdown.splitlines():
        lines.append(_MD_LINE_PREFIX.sub("", line))
    return "\n".join(lines)


def convert_markdown_to_json(markdown: str) -> str:
    """
    Wrap the Markdown schema report in a JSON object.

    The JSON payload uses a single top-level key "schema_report" whose value
    is the original Markdown string.

    Args:
        markdown: The Markdown-formatted schema report text.

    Returns:
        A pretty-printed JSON string containing the schema report under the
        "schema_report" key.
    """
    payload: Dict[str, Any] = {"schema_report": markdown}
    return json.dumps(payload, indent=2, sort_keys=True)


def write_atomic(target: Path, content: str) -> None:
    """
    Atomically write text content to the given file path.

    Creates parent directories as needed, writes to a temporary file
    alongside the target, then renames it into place. On failure during
    the final replace, the temporary file is removed and the exception is
    propagated.
    """
    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target.with_suffix(target.suffix + ".tmp")

    # Best-effort cleanup of any pre-existing temp file
    try:
        tmp_path.unlink()
    except FileNotFoundError:
        # Temp file does not exist; nothing to clean up
        pass

    # Write content to the temporary file
    tmp_path.write_text(content, encoding="utf-8")

    # Atomically move the temp file into place
    try:
        tmp_path.replace(target)
    except Exception:
        # Clean up temp file on failure before re-raising
        try:
            tmp_path.unlink()
        finally:
            raise


def generate_report(
    logger: logging.Logger, fmt: OutputFormat, output: Path | None
) -> None:
    """
    Generate a schema report and write it to the given file path or stdout.

    Args:
        logger: Logger instance to record diagnostics.
        fmt: Desired output format.
        output: Destination file path. If None, writes to stdout.

    Raises:
        CLIError: If generation, formatting, or writing fails.
    """
    logger.info("Generating schema report with format: %s", fmt.value)
    try:
        graph = create_sample_database()
        report = generate_schema_report(graph)

        if fmt is OutputFormat.MARKDOWN:
            formatted = report
        elif fmt is OutputFormat.TEXT:
            formatted = convert_markdown_to_plain_text(report)
        elif fmt is OutputFormat.JSON:
            formatted = convert_markdown_to_json(report)
        else:
            raise ValueError(f"Unsupported format: {fmt!r}")

        if output:
            write_atomic(output, formatted)
            logger.info("Report written to: %s", output)
        else:
            sys.stdout.write(formatted)
            if not formatted.endswith("\n"):
                sys.stdout.write("\n")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate schema report.")
        raise CLIError("Report generation failed. Check logs for details.") from exc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """
    Run the Schema Report CLI.

    The function parses CLI options, configures logging, invokes report
    generation, and handles user-facing errors.

    Args:
        argv: Optional argument list (defaults to sys.argv parsing).

    Returns:
        Exit code: 0 on success, 1 on failure, 130 on KeyboardInterrupt.
    """
    try:
        args = parse_arguments(argv)
        logger = configure_logging(args.verbose)

        if args.verbose:
            logger.debug("Verbose logging enabled.")

        generate_report(logger, args.fmt, args.output)
        logger.info("Schema report generation completed successfully.")
        return 0
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Unexpected error occurred.")
        print(
            "Error: An unexpected error occurred. Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
