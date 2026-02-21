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
import sys
from pathlib import Path

# Ensure project root is on sys.path before importing src.*
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.sample_data import create_sample_database  # noqa: E402
from src.reports.schema_report import generate_schema_report  # noqa: E402

# Configure logging for detailed diagnostics
LOG_PATH = Path(__file__).resolve().parent / "schema_report_cli.log"

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


class OutputFormat(enum.Enum):
    """Constrained enum for valid output formats."""

    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"

    def __str__(self) -> str:
        return self.value


class CLIError(Exception):
    """Base exception for CLI errors with user-friendly messages."""


def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Returns:
        argparse.Namespace: Validated argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Generate schema reports for financial asset relationships",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fmt",
        type=str,
        choices=[f.value for f in OutputFormat],
        default=OutputFormat.MARKDOWN.value,
        help="Output format (default: %(default)s)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: stdout)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def convert_markdown_to_plain_text(markdown: str) -> str:
    """
    Naive Markdown-to-text conversion for CLI output.

    Strips a few common Markdown markers but keeps content intact.
    """
    lines = []
    for line in markdown.splitlines():
        stripped = line.lstrip("# ").lstrip("- ").lstrip("* ")
        lines.append(stripped)
    return "\n".join(lines)


def convert_markdown_to_json(markdown: str) -> str:
    """
    Wrap the Markdown report in a simple JSON structure.

    This is a minimal implementation that can be extended later.
    """
    payload = {"schema_report": markdown}
    return json.dumps(payload, indent=2)


def generate_report(fmt: OutputFormat, output: Path | None) -> None:
    """
    Generate and output the schema report.

    Args:
        fmt: Output format enum value.
        output: Optional output file path.

    Raises:
        CLIError: If report generation fails.
    """
    try:
        logger.info("Generating schema report with format: %s", fmt.value)
        graph = create_sample_database()
        report = generate_schema_report(graph)

        if fmt is OutputFormat.MARKDOWN:
            formatted = report
        elif fmt is OutputFormat.TEXT:
            formatted = convert_markdown_to_plain_text(report)
        elif fmt is OutputFormat.JSON:
            formatted = convert_markdown_to_json(report)
        else:
            # Should never reach here due to enum validation
            raise ValueError(f"Unsupported format: {fmt}")

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(formatted, encoding="utf-8")
            logger.info("Report written to: %s", output)
        else:
            sys.stdout.write(formatted + ("\n" if not formatted.endswith("\n") else ""))

    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate schema report")
        raise CLIError("Report generation failed. Check logs for details.") from exc


def main() -> int:
    """
    Main entry point with proper exception handling.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    try:
        args = parse_arguments()

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled")

        try:
            output_format = OutputFormat(args.fmt)
            logger.debug("Using output format: %s", output_format)
        except ValueError:
            logger.error("Invalid format value: %s", args.fmt)
            print(
                "Error: Invalid output format. Please use one of: markdown, text, json",
                file=sys.stderr,
            )
            return 1

        generate_report(output_format, args.output)
        logger.info("Schema report generation completed successfully")
        return 0

    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        # Remove partial output file if it was being written
        if "args" in locals() and getattr(args, "output", None):
            output_path = Path(args.output)
            if output_path.exists():
                output_path.unlink()
                logger.debug("Removed partial output file: %s", output_path)
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error occurred")
        print(
            "Error: An unexpected error occurred. Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
