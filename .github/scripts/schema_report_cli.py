#!/usr/bin/env python3
"""
Schema Report CLI - Generate financial asset relationship schema reports.

This CLI tool generates schema reports with validated input options and
proper error handling that presents generic errors to users while maintaining
detailed diagnostics in logs.
"""

import argparse
import enum
import logging
import sys
from pathlib import Path
from typing import NoReturn, Optional

from src.data.sample_data import create_sample_database
from src.reports.schema_report import generate_schema_report

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# Configure logging for detailed diagnostics
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(".github/scripts/schema_report_cli.log"),
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

    pass


def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Returns:
        Validated argument namespace.
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


def generate_report(fmt: str, output: Optional[Path]) -> None:
    """
    Generate and output the schema report.

    Args:
        fmt: Output format (validated enum value).
        output: Optional output file path.

    Raises:
        CLIError: If report generation fails.
    """
    try:
        logger.info(f"Generating schema report with format: {fmt}")
        graph = create_sample_database()
        report = generate_schema_report(graph)

        # Format conversion (currently only markdown is supported)
        if fmt != OutputFormat.MARKDOWN.value:
            logger.warning(f"Format '{fmt}' not yet implemented, using markdown")

        # Output report
        if output:
            output.write_text(report)
            logger.info(f"Report written to: {output}")
        else:
            print(report)

    except Exception as e:
        logger.exception("Failed to generate schema report")
        raise CLIError("Report generation failed. Check logs for details.") from e


def main() -> int:
    """
    Main entry point with proper exception handling.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    try:
        args = parse_arguments()

        # Configure logging level
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled")

        # Validate format (already validated by argparse choices, but convert to enum)
        try:
            output_format = OutputFormat(args.fmt)
            logger.debug(f"Using output format: {output_format}")
        except ValueError as e:
            logger.error(f"Invalid format value: {args.fmt}")
            print(
                "Error: Invalid output format. Please use one of: markdown, text, json",
                file=sys.stderr,
            )
            return 1

        # Generate report
        generate_report(args.fmt, args.output)
        logger.info("Schema report generation completed successfully")
        return 0

    except CLIError as e:
        # User-friendly error message (generic)
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except Exception as e:
        # Catch-all for unexpected errors - log details but show generic message
        logger.exception("Unexpected error occurred")
        print(
            "Error: An unexpected error occurred. Please check the logs for details.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
