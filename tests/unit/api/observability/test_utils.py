"""Utility helpers for observability unit tests."""

import logging

import pytest
import structlog


def get_processor_handler() -> logging.Handler:
    """
    Find the logging handler configured with structlog's ProcessorFormatter.

    Returns:
        logging.Handler: The handler if found.

    Raises:
        pytest.fail: If no such handler is found.
    """
    root_logger = logging.getLogger()
    try:
        return next(h for h in root_logger.handlers if isinstance(h.formatter, structlog.stdlib.ProcessorFormatter))
    except StopIteration:
        pytest.fail("ProcessorFormatter handler not found")
        raise RuntimeError("Unreachable")
