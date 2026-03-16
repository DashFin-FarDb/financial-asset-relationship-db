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
import sys
import tempfile
from pathlib import Path

# Ensure project root is on sys.path before importing src.*
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.sample_data import (  # noqa: E402  # pylint: disable=import-error  # type: ignore[import-not-found]
    create_sample_database,
)
from src.reports.schema_report import (  # noqa: E402  # pylint: disable=import-error  # type: ignore[import-not-found]
    generate_schema_report,
)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOG_FILE_NAME = "schema_report_cli.log"

# Allow override via SCHEMA_REPORT_LOG env var; fall back to repo path or temp.
_env_log = os.getenv("SCHEMA_REPORT_LOG")
_default_log_path = Path(__file__).resolve().parent / LOG_FILE_NAME

if _env_log:
    LOG_PATH = Path(_env_log)
else:
    # Prefer repo location if writable; otherwise use system temp.
    try:
        _default_log_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = _default_log_path.parent / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        LOG_PATH = _default_log_path
    except Exception:
        LOG_PATH = Path(tempfile.gettempdir()) / LOG_FILE_NAME

# Ensure parent directory for LOG_PATH exists; if not, fallback to temp.
try:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_PATH = Path(tempfile.gettempdir()) / LOG_FILE_NAME
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(LOG_PATH)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

stream_handler = logging.StreamHandler(sys.stderr)
stream_formatter = logging.Formatter("%(levelname)s: %(message)s")
stream_handler.setFormatter(stream_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)  # Default; adjusted in main().

# ---------------------------------------------------------------------------
# CLI types and errors
# ---------------------------------------------------------------------------


class OutputFormat(enum.Enum):
    """Constrained enum for valid output formats."""

    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"

    def __str__(self) -> str:
        return self.value


class CLIError(Exception):
    """Base exception for CLI errors with user-friendly messages."""


DEFAULT_OUTPUT_FILENAMES = {
    OutputFormat.MARKDOWN: "schema_report.md",
    OutputFormat.TEXT: "schema_report.txt",
    OutputFormat.JSON: "schema_report.json",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    """
    Parse CLI arguments for the schema report tool.

    Recognized options:
    - --fmt: output format (markdown, text, json); defaults to markdown
    - --output / -o: write the report to a default file in the current working directory
    - --verbose / -v: enable verbose logging

    Returns:
        argparse.Namespace: Parsed arguments with attributes `fmt`, `output`, and `verbose`.
    """
    parser = argparse.ArgumentParser(
        description=("Generate schema reports for financial asset relationships."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fmt",
        type=str,
        choices=[f.value for f in OutputFormat],
        default=OutputFormat.MARKDOWN.value,
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write report to the specified output file path.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    return parser.parse_args()


def convert_markdown_to_plain_text(markdown: str) -> str:
    """
    Produce a simple plain-text representation of Markdown content.

    Strips common Markdown markers (e.g., leading '#', '-', '*') from the start of each line; does not perform full Markdown parsing and may not handle complex constructs correctly.

    Parameters:
        markdown (str): The Markdown text to convert.

    Returns:
        plain_text (str): The resulting plain-text string with leading Markdown markers removed from each line.
    """
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.lstrip("# ").lstrip("- ").lstrip("* ")
        lines.append(stripped)
    return "\n".join(lines)


def convert_markdown_to_json(markdown: str) -> str:
    """
    Embed the given Markdown report under the `schema_report` key in a JSON object.

    Parameters:
        markdown (str): The Markdown-formatted schema report content to wrap.

    Returns:
        json_str (str): A pretty-printed JSON string containing the Markdown under the `schema_report` key.
    """
    payload = {"schema_report": markdown}
    return json.dumps(payload, indent=2)


def default_output_path(fmt: OutputFormat) -> Path:
    """
    Return the default output file path for the given output format in the current working directory.

    Parameters:
        fmt (OutputFormat): The desired output format.

    Returns:
        Path: Resolved path to the default filename for `fmt` in the current working directory.

    Raises:
        CLIError: If `fmt` is not a supported OutputFormat.
    """
    filename = DEFAULT_OUTPUT_FILENAMES.get(fmt)
    if filename is None:
        raise CLIError(f"Unsupported format: {fmt!r}")
    return Path.cwd().resolve() / filename


def parse_output_format(value: str) -> OutputFormat | None:
    """
    Parse a string into an OutputFormat enum value.

    Parameters:
        value (str): The format name to parse; expected values are "markdown", "text", or "json".

    Returns:
        OutputFormat | None: The corresponding OutputFormat on success, `None` if the value is invalid.

    Notes:
        On invalid input a user-facing error message is printed to stderr.
    """
    try:
        output_format = OutputFormat(value)
        logger.debug("Using output format: %s", output_format)
        return output_format
    except ValueError:
        logger.error("Invalid format value: %s", value)
        print(
            "Error: Invalid output format. Please use one of: markdown, text, json.",
            file=sys.stderr,
        )
        return None


def cleanup_partial_output(temp_path: Path | None) -> None:
    """
    Remove a partially written temporary file if one exists.

    If `temp_path` is `None` the function is a no-op. If the path exists the file is deleted; errors during removal are ignored (the function does not raise).
    Parameters:
        temp_path (Path | None): Path to the temporary file to remove, or `None` to indicate no file.
    """
    if temp_path is None:
        return

    try:
        if temp_path.exists():
            temp_path.unlink()
            logger.debug(
                "Removed partial temporary file: %s",
                temp_path,
            )
    except OSError:
        logger.debug("Failed to remove partial file: %s", temp_path)


def format_report_content(fmt: OutputFormat, report: str) -> str:
    """
    Format a markdown schema report into the selected output format.

    Parameters:
        fmt (OutputFormat): Desired output format (MARKDOWN, TEXT, or JSON).
        report (str): Report content in Markdown.

    Returns:
        str: The report transformed to the chosen format (Markdown unchanged, plain text for TEXT, JSON-wrapped string for JSON).

    Raises:
        ValueError: If `fmt` is not a supported OutputFormat.
    """
    if fmt is OutputFormat.MARKDOWN:
        return report
    if fmt is OutputFormat.TEXT:
        return convert_markdown_to_plain_text(report)
    if fmt is OutputFormat.JSON:
        return convert_markdown_to_json(report)
    raise ValueError(f"Unsupported format: {fmt!r}")


def write_atomic(path: Path, data: str, encoding: str = "utf-8") -> None:
    """
    Atomically write text data to the given path.

    Ensures the target directory exists, writes `data` to a temporary file in the same directory, flushes and syncs the file to disk, and then atomically replaces the target path with the temporary file. If an error occurs during writing or replacement, any partial temporary file is removed and the original exception is re-raised.

    Parameters:
        path (Path): Destination file path to write.
        data (str): Text content to write to the file.
        encoding (str): Text encoding to use when writing (default: "utf-8").
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(dir=str(parent))
    tmp_path = Path(tmp_path_str)

    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(path)
    except BaseException:
        cleanup_partial_output(tmp_path)
        raise


def generate_report(fmt: OutputFormat, output: Path | None) -> None:
    """
    Generate a schema report and write it to stdout or a file.

    Args:
        fmt: Selected output format.
        output: Optional output file path. If None, print to stdout.

    Raises:
        CLIError: If report generation or formatting fails.
    """
    logger.info("Generating schema report with format: %s", fmt.value)
    try:
        graph = create_sample_database()
        report = generate_schema_report(graph)
        formatted = format_report_content(fmt, report)

        if output:
            write_atomic(output, formatted)
            logger.info("Report written to: %s", output)
        else:
            # Ensure trailing newline for clean CLI output.
            sys.stdout.write(formatted + ("\n" if not formatted.endswith("\n") else ""))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate schema report.")
        raise CLIError("Report generation failed. Check logs for details.") from exc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Run the CLI: parse arguments, configure logging, generate the schema report, and return an exit code.

    Parses command-line arguments, adjusts logger and handler levels according to the verbose flag, validates the chosen output format, invokes report generation (optionally writing to the default output file), and maps common error conditions to user-facing exit codes while logging diagnostic details.

    Returns:
        int: Exit code — 0 on success; 1 on validation or unexpected errors; 130 if cancelled by the user.
    """
    try:
        args = parse_arguments()

        # Adjust handler levels depending on verbose flag.
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            stream_handler.setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled.")
        else:
            # Keep DEBUG and traces in the log file only.
            stream_handler.setLevel(logging.WARNING)
            logger.setLevel(logging.INFO)

        output_format = parse_output_format(args.fmt)
        if output_format is None:
            return 1

        safe_output = args.output
        generate_report(output_format, safe_output)
        logger.info("Schema report generation completed successfully.")
        return 0

    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except (IOError, OSError, RuntimeError, TypeError, ValueError):
        logger.exception("Unexpected error occurred.")
        print(
            "Error: An unexpected error occurred. " + "Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
