"""Unit tests for the structured logging framework configuration."""

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest
import structlog

import src.observability.logging
from src.config.settings import get_settings
from src.observability.context import reset_request_context, set_request_context
from src.observability.logging import _inject_request_context, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset the standard library logging and structlog after each test."""
    # Reset our internal initialization flag to allow reconfiguration in tests
    src.observability.logging._logging_initialized = False

    # Clear settings cache to allow environment variable overrides
    get_settings.cache_clear()
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    yield

    # Restore original state
    root_logger.handlers.clear()
    for handler in original_handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(original_level)

    # Fully reset structlog
    structlog.reset_defaults()
    # Also clear any cached loggers if possible, though reset_defaults usually helps.


def test_inject_request_context_processor():
    """Test that the custom processor injects request context correctly."""
    # Set context variables using the tokens from Task 1.1
    tokens = set_request_context(request_id="req-123", correlation_id="corr-456")
    try:
        # Create an initial event dictionary
        event_dict = {"event": "test event", "level": "info"}

        # Run the processor (passing None for logger as it's common in tests)
        result = _inject_request_context(None, "info", event_dict)

        # Assert context was injected
        assert result["request_id"] == "req-123"
        assert result["correlation_id"] == "corr-456"
        assert result["event"] == "test event"
        assert result["level"] == "info"
    finally:
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
    # We now skip pytest handlers, so we check that at least one handler has our formatter
    assert len(root_logger.handlers) >= 1
    assert any(isinstance(h.formatter, structlog.stdlib.ProcessorFormatter) for h in root_logger.handlers)
    assert root_logger.level == logging.INFO


def test_stdlib_logging_emits_json_with_context_and_extra():
    """
    Test that calling the standard library logger emits structured JSON,
    includes the request context, AND preserves extra fields.
    """
    # 1. Setup our structured logging
    setup_logging()

    # 2. Redirect root logger output to a string buffer instead of sys.stderr
    log_output = StringIO()
    stream_handler = logging.StreamHandler(log_output)

    # We need to extract the formatter configured by setup_logging
    root_logger = logging.getLogger()

    # Find our handler
    our_handler = next(h for h in root_logger.handlers if isinstance(h.formatter, structlog.stdlib.ProcessorFormatter))
    stream_handler.setFormatter(our_handler.formatter)

    # Temporary clear all handlers for this test to avoid interference
    original_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    # 3. Set the context
    tokens = set_request_context(request_id="req-999", correlation_id="corr-888")

    try:
        # 4. Emit a log using the standard library with an 'extra' field
        logger = logging.getLogger("test.module")
        logger.info("This is a test message", extra={"custom_field": "value", "user_ref": "USR123"})

        # 5. Extract and parse the JSON output
        output_str = log_output.getvalue()
        assert output_str, "Log output should not be empty"

        # If there are multiple lines (e.g. from other background logs), take the last one
        last_line = output_str.strip().split("\n")[-1]
        log_data = json.loads(last_line)

        # 6. Verify the payload
        assert log_data["event"] == "This is a test message"
        assert log_data["logger"] == "test.module"
        assert log_data["level"] == "info"
        assert log_data["request_id"] == "req-999"
        assert log_data["correlation_id"] == "corr-888"
        assert log_data["custom_field"] == "value"
        assert log_data["user_ref"] == "USR123"
        assert "timestamp" in log_data
    finally:
        # Restore handlers
        root_logger.handlers.clear()
        for h in original_handlers:
            root_logger.addHandler(h)

        reset_request_context(tokens)


def test_setup_logging_invalid_level(capsys):
    """Test that setup_logging handles invalid LOG_LEVEL with a warning."""
    with patch.dict(os.environ, {"LOG_LEVEL": "DEUBG"}):
        get_settings.cache_clear()
        setup_logging()

    captured = capsys.readouterr()
    # Note: setup_logging uses print for the warning since it's before logging is fully up
    assert "WARNING: Invalid LOG_LEVEL 'DEUBG', defaulting to INFO" in captured.out

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_setup_logging_idempotency():
    """Test that setup_logging only runs once unless forced."""
    with patch("src.observability.logging.structlog.configure") as mock_configure:
        setup_logging()
        setup_logging()
        # Should only be called once because of the internal flag
        assert mock_configure.call_count == 1
