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

from src.data.sample_data import create_sample_database  # noqa: E402
from src.reports.schema_report import generate_schema_report  # noqa: E402

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

# Allow override via SCHEMA_REPORT_LOG env var; fall back to repo path or temp.
_env_log = os.getenv("SCHEMA_REPORT_LOG")
_default_log_path = Path(__file__).resolve().parent / "schema_report_cli.log"

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
        LOG_PATH = Path(tempfile.gettempdir()) / "schema_report_cli.log"

# Ensure parent directory for LOG_PATH exists; if not, fallback to temp.
try:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    LOG_PATH = Path(tempfile.gettempdir()) / "schema_report_cli.log"
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
        """
        Get the enum member's underlying string value.
        
        Returns:
            The string value associated with this enum member.
        """
        return self.value


class CLIError(Exception):
    """Base exception for CLI errors with user-friendly messages."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the Schema Report CLI.
    
    Recognizes:
    - --fmt: output format, one of 'markdown', 'text', or 'json' (default: 'markdown').
    - --output / -o: optional filesystem path to write the report; if omitted, stdout is used.
    - --verbose / -v: enable verbose logging.
    
    Returns:
        argparse.Namespace: Parsed arguments with attributes `fmt` (str), `output` (Path | None), and `verbose` (bool).
    """
    parser = argparse.ArgumentParser(
        description="Generate schema reports for financial asset relationships.",
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
        help="Output file path (default: stdout).",
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
    Produce a plain-text version of a Markdown string.
    
    Removes common leading Markdown markers (heading hashes '#' and list markers '-' or '*') from each line while preserving the original line breaks and content.
    
    Parameters:
        markdown (str): Input Markdown text.
    
    Returns:
        str: Plain-text string with leading Markdown markers removed and lines joined by newline characters.
    """
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.lstrip("# ").lstrip("- ").lstrip("* ")
        lines.append(stripped)
    return "\n".join(lines)


def convert_markdown_to_json(markdown: str) -> str:
    """
    Create a JSON payload containing the provided Markdown schema report.
    
    Parameters:
        markdown (str): The Markdown schema report to include in the payload.
    
    Returns:
        json_str (str): Pretty-printed JSON string with a top-level `schema_report` field holding the original Markdown.
    """
    payload = {"schema_report": markdown}
    return json.dumps(payload, indent=2)


def write_atomic(path: Path, data: str, encoding: str = "utf-8") -> None:
    """
    Write text to `path` atomically.
    
    Creates parent directories if needed, writes `data` to a temporary file in the same directory, flushes and syncs contents to disk, then atomically replaces the destination with the temporary file. On failure the temporary file is removed when possible and the original exception is propagated.
    
    Parameters:
        path (Path): Destination file path.
        data (str): Text content to write.
        encoding (str): File encoding to use (default "utf-8").
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
    except Exception:
        try:
            tmp_path.unlink()
        except Exception:
            pass
        raise


def generate_report(fmt: OutputFormat, output: Path | None) -> None:
    """
    Generate a schema report and write it to the given file path or stdout.
    
    Parameters:
        fmt (OutputFormat): Desired output format (MARKDOWN, TEXT, or JSON).
        output (Path | None): Destination file path. If None, writes to stdout.
    
    Raises:
        CLIError: If report generation, formatting, or writing fails.
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
    Run the Schema Report CLI: parse arguments, configure logging, validate options, generate the report, and handle errors.
    
    Parses CLI options, adjusts logging verbosity, validates the requested output format, invokes report generation, and prints user-facing error or cancellation messages when appropriate.
    
    Returns:
        int: Process exit code — `0` for success, `1` for general errors (invalid options, CLIError, or unexpected failures), `130` if cancelled by the user (KeyboardInterrupt).
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

        try:
            output_format = OutputFormat(args.fmt)
            logger.debug("Using output format: %s", output_format)
        except ValueError:
            logger.error("Invalid format value: %s", args.fmt)
            print(
                "Error: Invalid output format. " "Please use one of: markdown, text, json.",
                file=sys.stderr,
            )
            return 1

        generate_report(output_format, args.output)
        logger.info("Schema report generation completed successfully.")
        return 0

    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        # Attempt to remove any partial output file being written.
        # Atomic writes avoid partial target files; do not delete existing outputs here.
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error occurred.")
        print(
            "Error: An unexpected error occurred. Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())