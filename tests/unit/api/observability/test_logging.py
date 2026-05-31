"""Unit tests for the structured logging framework configuration."""

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest
import structlog

from api.observability.context import set_request_context
from api.observability.logging import _inject_request_context, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset the standard library logging and structlog after each test."""
    # Store original handlers and level
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    yield

    # Restore original state
    root_logger.handlers.clear()
    for handler in original_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(original_level)
    structlog.reset_defaults()


def test_inject_request_context_processor():
    """Test that the custom processor injects request context correctly."""
    # Set context variables using the tokens from Task 1.1
    tokens = set_request_context(request_id="req-123", correlation_id="corr-456")
    try:
        # Create an initial event dictionary
        event_dict = {"event": "test event", "level": "info"}

        # Run the processor
        result = _inject_request_context(None, "info", event_dict)

        # Assert context was injected
        assert result["request_id"] == "req-123"
        assert result["correlation_id"] == "corr-456"
        assert result["event"] == "test event"
        assert result["level"] == "info"
    finally:
        # Reset context (even though the test runner isolates contextvars in modern pytest-asyncio,
        # it's good practice when testing ContextVars directly)
        from api.observability.context import reset_request_context

        reset_request_context(tokens)


def test_inject_request_context_processor_empty():
    """Test the processor handles empty context safely."""
    # ContextVars default to None
    event_dict = {"event": "test event"}
    result = _inject_request_context(None, "info", event_dict)

    # Missing context vars should not be added to the dictionary
    assert "request_id" not in result
    assert "correlation_id" not in result
    assert result["event"] == "test event"


def test_setup_logging_configures_root_logger():
    """Test that setup_logging configures the root logger to use structlog."""
    setup_logging()

    root_logger = logging.getLogger()
    assert len(root_logger.handlers) == 1
    assert root_logger.level == logging.INFO

    # Check the formatter is our structlog ProcessorFormatter
    handler = root_logger.handlers[0]
    assert isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter)


def test_stdlib_logging_emits_json_with_context():
    """
    Test that calling the standard library logger emits structured JSON
    and includes the request context.
    """
    # 1. Setup our structured logging
    setup_logging()

    # 2. Redirect root logger output to a string buffer instead of sys.stderr
    log_output = StringIO()
    stream_handler = logging.StreamHandler(log_output)

    # We need to extract the formatter configured by setup_logging
    root_logger = logging.getLogger()
    formatter = root_logger.handlers[0].formatter
    stream_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    # 3. Set the context
    tokens = set_request_context(request_id="req-999", correlation_id="corr-888")

    try:
        # 4. Emit a log using the standard library
        logger = logging.getLogger("test.module")
        logger.info("This is a test message", extra={"custom_field": "value"})

        # 5. Extract and parse the JSON output
        output_str = log_output.getvalue()
        assert output_str, "Log output should not be empty"

        log_data = json.loads(output_str)

        # 6. Verify the payload
        assert log_data["event"] == "This is a test message"
        assert log_data["logger"] == "test.module"
        assert log_data["level"] == "info"
        assert log_data["request_id"] == "req-999"
        assert log_data["correlation_id"] == "corr-888"
        assert "timestamp" in log_data
    finally:
        from api.observability.context import reset_request_context

        reset_request_context(tokens)


def test_structlog_logging_emits_json_with_context():
    """Test that calling structlog logger emits structured JSON and includes context without double-serialization."""
    setup_logging()

    log_output = StringIO()
    stream_handler = logging.StreamHandler(log_output)

    root_logger = logging.getLogger()
    formatter = root_logger.handlers[0].formatter
    stream_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    tokens = set_request_context(request_id="req-111", correlation_id="corr-222")

    try:
        logger = structlog.get_logger("test.structlog")
        logger.info("This is a structlog message")

        output_str = log_output.getvalue()
        assert output_str, "Log output should not be empty"

        log_data = json.loads(output_str)

        assert log_data["event"] == "This is a structlog message"
        assert log_data["logger"] == "test.structlog"
        assert log_data["level"] == "info"
        assert log_data["request_id"] == "req-111"
        assert log_data["correlation_id"] == "corr-222"
        assert "timestamp" in log_data
    finally:
        from api.observability.context import reset_request_context

        reset_request_context(tokens)
