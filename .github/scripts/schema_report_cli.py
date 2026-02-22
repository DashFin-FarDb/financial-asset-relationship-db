#!/usr/bin/env python3
"""
Schema Report CLI

A command-line interface for generating schema reports from the financial asset relationship database.
Validates inputs early and provides user-friendly error messages with detailed logging.
"""

import argparse
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.sample_data import create_sample_database  # noqa: E402
from src.reports.schema_report import generate_schema_report  # noqa: E402


class OutputFormat(str, Enum):
    """Supported output formats for schema reports."""

    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"

    @classmethod
    def choices(cls):
        """Return a list of valid format choices."""
        return [fmt.value for fmt in cls]


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the CLI.

    Args:
        verbose (bool): If True, set log level to DEBUG; otherwise INFO.

    Returns:
        logging.Logger: Configured logger instance.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    # Use absolute path relative to script location
    log_file = Path(__file__).parent / "schema_report_cli.log"
    handlers = [logging.FileHandler(log_file)]

    # Only add stderr handler in verbose mode
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    return logging.getLogger(__name__)


def format_as_json(metrics: Dict[str, Any]) -> str:
    """Format metrics as a JSON string.

    Args:
        metrics: Dictionary of calculated metrics.
    """
    return json.dumps(metrics, indent=2, default=str)


def format_as_text(report: str) -> str:
    """Format report as plain text by stripping markdown formatting."""
    import re

    # Remove markdown headers
    text = re.sub(r"^#+\s+", "", report, flags=re.MULTILINE)
    # Remove bold formatting
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Remove list markers
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    return text


def generate_report(fmt: OutputFormat, logger: logging.Logger) -> str:
    """Generate a schema report in the specified format.

    Args:
        fmt (OutputFormat): Desired output format for the report. Supported values
            are ``OutputFormat.MARKDOWN``, ``OutputFormat.JSON``, and
            ``OutputFormat.TEXT``.
        logger (logging.Logger): Logger instance used for progress and error
            reporting during report generation.

    Returns:
        str: The generated report content. For ``OutputFormat.JSON`` this is a
        JSON-formatted string of the calculated metrics. For
        ``OutputFormat.MARKDOWN`` this is a Markdown-formatted schema report.
        For ``OutputFormat.TEXT`` this is a plain-text version of the Markdown
        report with formatting removed.

    Raises:
        ValueError: If report generation fails for any reason. The original
        exception is attached as the cause.
    """
    logger.info(f"Generating schema report in {fmt.value} format")

    try:
        # Create sample database
        logger.debug("Creating sample database")
        graph = create_sample_database()

        if fmt == OutputFormat.JSON:
            # For JSON, return metrics directly
            logger.debug("Calculating metrics for JSON output")
            metrics = graph.calculate_metrics()
            return format_as_json(metrics)
        else:
            # Generate markdown report
            logger.debug("Generating markdown report")
            report = generate_schema_report(graph)

            if fmt == OutputFormat.TEXT:
                logger.debug("Converting markdown to plain text")
                return format_as_text(report)
            else:  # OutputFormat.MARKDOWN
                return report

    except Exception as e:
        logger.error(
            f"Failed to generate report: {type(e).__name__}: {e}", exc_info=True
        )
        raise ValueError("Report generation failed") from e


def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate schema reports from financial asset relationship database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --fmt markdown
  %(prog)s --fmt json --output report.json
  %(prog)s --fmt text --verbose
        """,
    )

    parser.add_argument(
        "--fmt",
        type=str,
        choices=OutputFormat.choices(),
        default=OutputFormat.MARKDOWN.value,
        help=f"Output format (default: {OutputFormat.MARKDOWN.value})",
    )

    parser.add_argument(
        "--output", "-o", type=str, help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    return parser.parse_args()


def main() -> int:
    # Parse arguments (argparse will handle --help and validation errors)
    """def main() -> int:

    Main CLI entry point.  This function serves as the main entry point for the
    command-line interface (CLI) of the schema report generator.  It handles
    argument parsing, logging setup, and the generation of the report based on the
    specified output format.  The function also manages output writing, either to a
    specified file or to standard output, and includes error handling  for invalid
    formats and I/O operations. Additionally, it gracefully handles user
    interruptions and unexpected errors.
    """
    args = parse_arguments()

    # Setup logging
    logger = setup_logging(args.verbose)
    logger.info("Schema Report CLI started")

    try:
        # Validate and convert format
        try:
            fmt = OutputFormat(args.fmt)
        except ValueError:
            # This should not happen due to argparse choices, but defensive programming
            logger.error(f"Invalid format specified: {args.fmt}")
            print(
                f"Error: Invalid output format. Supported formats: {', '.join(OutputFormat.choices())}",
                file=sys.stderr,
            )
            return 1

        # Generate report
        report = generate_report(fmt, logger)

        # Write output
        if args.output:
            logger.info(f"Writing report to {args.output}")
            try:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(report, encoding="utf-8")
                logger.info(f"Report successfully written to {args.output}")
            except IOError as e:
                logger.error(f"Failed to write output file: {e}", exc_info=True)
                print(
                    "Error: Failed to write output file. Check logs for details.",
                    file=sys.stderr,
                )
                return 1
        else:
            # Write to stdout
            print(report)

        logger.info("Schema report generation completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # Catch-all for unexpected errors
        logger.critical(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        print(
            "Error: An unexpected error occurred. Check logs at .github/scripts/schema_report_cli.log for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
