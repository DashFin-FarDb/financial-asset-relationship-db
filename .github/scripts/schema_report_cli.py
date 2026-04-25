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

_PROJECT_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", ".git")


def _find_project_root(start: Path) -> Path:
    """Walk upward from *start* to find the project root directory.

    Parameters:
        start: Directory at which to begin the upward search.

    Returns:
        The first ancestor directory that contains a recognised project marker.

    Raises:
        RuntimeError: If no project root can be located.
    """
    current = start.resolve()
    while True:
        if any((current / marker).exists() for marker in _PROJECT_MARKERS):
            return current
        parent = current.parent
        if parent == current:
            raise RuntimeError(f"Could not determine project root starting from {start}")
        current = parent


# Ensure project root is on sys.path before importing src.*
try:
    PROJECT_ROOT = _find_project_root(Path(__file__).resolve().parent)
except RuntimeError:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.data.sample_data import (  # noqa: E402  # pylint: disable=import-error  # type: ignore[import-not-found]
    create_sample_database,
)
from src.reports.schema_report import (  # noqa: E402  # pylint: disable=import-error  # type: ignore[import-not-found]
    generate_schema_report,
)

LOG_FILE_NAME = "schema_report_cli.log"
_env_log = os.getenv("SCHEMA_REPORT_LOG")
_default_log_path = Path(__file__).resolve().parent / LOG_FILE_NAME

if _env_log:
    LOG_PATH = Path(_env_log)
else:
    try:
        _default_log_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = _default_log_path.parent / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        LOG_PATH = _default_log_path
    except Exception:
        LOG_PATH = Path(tempfile.gettempdir()) / LOG_FILE_NAME

try:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_PATH = Path(tempfile.gettempdir()) / LOG_FILE_NAME
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

FILE_FORMATTER = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
STREAM_FORMATTER = logging.Formatter("%(levelname)s: %(message)s")


def _reset_logger_handlers(target_logger: logging.Logger) -> None:
    """Close and remove existing handlers so reloads do not duplicate them."""
    for handler in list(target_logger.handlers):
        target_logger.removeHandler(handler)
        try:
            handler.close()
        except OSError as exc:
            target_logger.debug("Ignoring handler close error during logger reset: %s", exc)


file_handler = logging.FileHandler(LOG_PATH)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(FILE_FORMATTER)

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(STREAM_FORMATTER)

logger = logging.getLogger(__name__)
_reset_logger_handlers(logger)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

FILE_LOGGER = logging.getLogger(__name__ + ".file")
_reset_logger_handlers(FILE_LOGGER)
FILE_LOGGER.addHandler(file_handler)
FILE_LOGGER.setLevel(logging.DEBUG)
FILE_LOGGER.propagate = False


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


def configure_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the CLI logger.

    Sets handler levels based on *verbose*.  Safe to call multiple times; does
    not add duplicate handlers.
    """
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.WARNING)
        logger.setLevel(logging.INFO)
    return logger


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the schema report CLI.

    Returns:
        argparse.Namespace with the following attributes:
            - fmt (OutputFormat): Converted enum instance (not string)
            - output (Path | None): Output file path or None for stdout
            - verbose (bool): Verbose logging flag

    Note:
        The fmt attribute is converted from string to OutputFormat enum
        during parsing. This allows better type safety in downstream code
        but means callers receive an enum, not the raw string argument.
        Invalid formats will cause argparse to exit with code 2.
    """
    parser = argparse.ArgumentParser(
        description=("Generate schema reports for financial asset relationships."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    valid_formats = [f.value for f in OutputFormat]
    parser.add_argument(
        "--fmt",
        type=str,
        choices=valid_formats,
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

    args = parser.parse_args()

    # Convert fmt string to OutputFormat enum for type safety
    args.fmt = OutputFormat(args.fmt)
    return args


def convert_markdown_to_plain_text(markdown: str) -> str:
    """Convert Markdown to a simple plain-text representation."""
    _leading_marker = re.compile(r"^(#{1,6}\s+|[-*]\s+)")
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = _leading_marker.sub("", line)
        lines.append(stripped)
    return "\n".join(lines)


def convert_markdown_to_json(markdown: str) -> str:
    """Embed a Markdown report under the schema_report key."""
    payload = {"schema_report": markdown}
    return json.dumps(payload, indent=2)


def default_output_path(fmt: OutputFormat) -> Path:
    """Return the default output file path for a given output format."""
    filename = DEFAULT_OUTPUT_FILENAMES.get(fmt)
    if filename is None:
        raise CLIError(f"Unsupported format: {fmt!r}")
    return Path.cwd().resolve() / filename


def cleanup_partial_output(temp_path: Path | None) -> None:
    """Remove a partially written temporary file if one exists."""
    if temp_path is None:
        return

    try:
        if temp_path.exists():
            temp_path.unlink()
            logger.debug("Removed partial temporary file: %s", temp_path)
    except OSError:
        logger.debug("Failed to remove partial file: %s", temp_path)


def format_report_content(fmt: OutputFormat, report: str) -> str:
    """Convert a Markdown schema report into the specified output format."""
    if fmt is OutputFormat.MARKDOWN:
        return report
    if fmt is OutputFormat.TEXT:
        return convert_markdown_to_plain_text(report)
    if fmt is OutputFormat.JSON:
        return convert_markdown_to_json(report)
    raise ValueError(f"Unsupported format: {fmt!r}")


def write_atomic(path: Path, data: str, encoding: str = "utf-8") -> None:
    """Atomically write text data to the given path with durability guarantee."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(dir=str(parent))
    tmp_path = Path(tmp_path_str)

    try:
        # Write through the file descriptor for durability
        # Loop to handle partial writes - os.write() may write fewer bytes than requested
        encoded_data = data.encode(encoding)
        bytes_written = 0
        while bytes_written < len(encoded_data):
            n = os.write(fd, encoded_data[bytes_written:])
            if n == 0:
                # os.write returning 0 indicates no progress can be made
                raise OSError("write returned 0, no progress possible")
            bytes_written += n
        os.fsync(fd)  # Ensure data is written to disk before rename
        os.close(fd)
        tmp_path.replace(path)

        # Fsync parent directory to ensure directory entry is durable
        # This is best-effort and platform-specific
        try:
            parent_fd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except (OSError, AttributeError):
            # Ignore errors on platforms that don't support directory fsync
            # or when O_RDONLY on directories is not supported
            pass
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass  # fd might already be closed
        cleanup_partial_output(tmp_path)
        raise


def generate_report(log: logging.Logger, fmt: OutputFormat, output: Path | None) -> None:
    """Generate the schema report and write it to the given file path or stdout."""
    log.info("Generating schema report with format: %s", fmt.value)
    try:
        graph = create_sample_database()
        report = generate_schema_report(graph)
        formatted = format_report_content(fmt, report)

        if output:
            write_atomic(output, formatted)
            log.info("Report written to: %s", output)
        else:
            sys.stdout.write(formatted + ("\n" if not formatted.endswith("\n") else ""))
    except Exception as exc:  # noqa: BLE001
        FILE_LOGGER.exception("Failed to generate schema report.")
        raise CLIError("Report generation failed. Check logs for details.") from exc


def main() -> int:
    """Execute the CLI and return an exit code."""
    try:
        args = parse_arguments()

        log = configure_logging(verbose=args.verbose)
        if args.verbose:
            log.debug("Verbose logging enabled.")

        output_format = args.fmt
        safe_output = args.output
        generate_report(log, output_format, safe_output)
        log.info("Schema report generation completed successfully.")
        return 0

    except SystemExit as exc:
        # argparse calls sys.exit() on invalid arguments; preserve the exit code
        if isinstance(exc.code, int):
            return exc.code
        return 1 if exc.code else 0

    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except Exception:  # noqa: BLE001
        FILE_LOGGER.exception("Unexpected error occurred.")
        print(
            "Error: An unexpected error occurred. Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
