import json
import logging
from io import StringIO

import pytest
import structlog

import src.observability.logging
from src.observability.events import ObservabilityEvent
from src.observability.logger import get_logger, log_event
from src.observability.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset the standard library logging and structlog after each test."""
    src.observability.logging._logging_initialized = False
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    yield
    root_logger.handlers.clear()
    for handler in original_handlers:
        root_logger.addHandler(handler)
    structlog.reset_defaults()


def test_log_event_outputs_correct_json_and_preserves_message():
    """
    Test that log_event produces correct JSON schema and maintains standard log message.
    """
    # 1. Setup structured logging
    setup_logging()
    log_output = StringIO()
    stream_handler = logging.StreamHandler(log_output)
    root_logger = logging.getLogger()

    # Find our handler configured by setup_logging
    our_handler = next(h for h in root_logger.handlers if isinstance(h.formatter, structlog.stdlib.ProcessorFormatter))
    stream_handler.setFormatter(our_handler.formatter)

    # Isolated handlers for this test
    original_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    try:
        logger = get_logger("test_observability")
        event = ObservabilityEvent(
            event="domain_event_slug",
            message="Human readable domain message",
            metadata={"job_id": "job-123", "user": "mo"},
        )

        # 2. Log the event
        log_event(logger, logging.INFO, event)

        # 3. Parse and verify output
        output_str = log_output.getvalue().strip()
        assert output_str, "Log output should not be empty"

        # Take the last line in case of noise
        last_line = output_str.split("\n")[-1]
        data = json.loads(last_line)

        # Verify top-level JSON keys as per requirements
        assert data["event"] == "domain_event_slug"
        assert data["message"] == "Human readable domain message"
        assert data["metadata"] == {"job_id": "job-123", "user": "mo"}

        # Verify standard fields
        assert data["logger"] == "test_observability"
        assert data["level"] == "info"
        assert "timestamp" in data

    finally:
        root_logger.handlers.clear()
        for h in original_handlers:
            root_logger.addHandler(h)


def test_standard_logging_does_not_contain_redundant_message_key():
    """
    Test that standard logging calls do not contain the 'message' key,
    ensuring the conditional migration prevents redundancy.
    """
    setup_logging()
    log_output = StringIO()
    stream_handler = logging.StreamHandler(log_output)
    root_logger = logging.getLogger()
    our_handler = next(h for h in root_logger.handlers if isinstance(h.formatter, structlog.stdlib.ProcessorFormatter))
    stream_handler.setFormatter(our_handler.formatter)
    original_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    try:
        logger = logging.getLogger("test_standard")
        logger.info("Standard log message")

        output_str = log_output.getvalue().strip()
        last_line = output_str.split("\n")[-1]
        data = json.loads(last_line)

        # event should be the message
        assert data["event"] == "Standard log message"
        # message key should NOT exist for standard logs
        assert "message" not in data
    finally:
        root_logger.handlers.clear()
        for h in original_handlers:
            root_logger.addHandler(h)


def test_log_event_caplog_compatibility(caplog):
    """
    Test that log_event is compatible with pytest caplog for human-readable messages.
    """
    logger = get_logger("test_caplog")
    event = ObservabilityEvent(
        event="test_slug",
        message="A message for caplog",
        metadata={"foo": "bar"},
    )

    with caplog.at_level(logging.INFO):
        log_event(logger, logging.INFO, event)

    # caplog.text should contain the human-readable message, not the slug
    assert "A message for caplog" in caplog.text
    assert "test_slug" not in caplog.text  # The slug should be in 'extra', not message

    # Verify the record itself
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.getMessage() == "A message for caplog"
    assert record.event == "test_slug"
    assert record.metadata == {"foo": "bar"}
