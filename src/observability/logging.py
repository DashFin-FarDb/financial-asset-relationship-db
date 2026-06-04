"""Centralized structured logging configuration using structlog.

This module provides the setup function to intercept standard library logging
and route it through a structlog pipeline that outputs JSON and injects
request context (correlation_id and request_id).
"""

import logging
import threading
from typing import Any

import structlog

from src.config.settings import get_settings

from .context import get_request_context

_logging_initialized_lock = threading.Lock()

_logging_initialized = False


def _inject_request_context(_logger: Any, _log_method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Inject request-scoped identifiers into the log event dictionary.

    If the current request context contains `request_id` or `correlation_id`, copies those keys into `event_dict`.

    Returns:
        dict: The `event_dict` updated with `request_id` and/or `correlation_id` when present.
    """
    context = get_request_context()
    if context.get("request_id"):
        event_dict["request_id"] = context["request_id"]
    if context.get("correlation_id"):
        event_dict["correlation_id"] = context["correlation_id"]
    return event_dict


def _move_event_to_message(_logger: Any, _log_method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Copy structured `event` into `message` for records that follow the ObservabilityEvent schema.

    If the underlying log record exposes `event` and `metadata`, and `event_dict` contains `"event"`
    but lacks `"message"`, sets `event_dict["message"]` to the value of `event_dict["event"]`.

    Returns:
        dict[str, Any]: The possibly modified `event_dict`.
    """
    record = event_dict.get("_record")
    if record and hasattr(record, "event") and hasattr(record, "metadata") and \
       "event" in event_dict and "message" not in event_dict:
        event_dict["message"] = event_dict["event"]
    return event_dict


def setup_logging() -> None:
    """
    Configure structlog and route standard library logging records through a structlog pipeline.

    Idempotent and thread-safe: subsequent calls are no-ops. This sets up shared processors and
    a ProcessorFormatter that renders JSON, installs a StreamHandler on the root logger, removes
    existing non-pytest handlers to avoid resource leaks, and sets the root logger level from
    get_settings().log_level (defaults to INFO if invalid).
    """
    global _logging_initialized
    with _logging_initialized_lock:
        if _logging_initialized:
            return

        # Configure structlog processors
        # We include ExtraAdder to support the 'extra' keyword in logging calls
        shared_processors: list[Any] = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _move_event_to_message,
            structlog.stdlib.ExtraAdder(),
            _inject_request_context,
            structlog.processors.dict_tracebacks,
        ]

        structlog.configure(
            processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Route standard library logging to structlog
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        log_level_str = get_settings().log_level.upper()
        log_level = getattr(logging, log_level_str, None)
        if not isinstance(log_level, int):
            log_level = logging.INFO
            # Using print because logging is not yet fully configured
            print(f"WARNING: Invalid LOG_LEVEL '{log_level_str}', defaulting to INFO")

        root_logger = logging.getLogger()

        # Safely clear and close existing handlers to prevent resource leaks.
        # We avoid removing pytest's LogCaptureHandler to prevent breaking tests.
        for h in list(root_logger.handlers):
            # Check for pytest LogCaptureHandler without direct dependency if possible
            h_module = h.__class__.__module__
            h_name = h.__class__.__name__
            if "pytest" in h_module or h_name == "LogCaptureHandler":
                continue

            try:
                h.close()
            except Exception:  # pylint: disable=broad-except
                pass
            root_logger.removeHandler(h)

        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

        _logging_initialized = True
