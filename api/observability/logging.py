"""Centralized structured logging configuration using structlog.

This module provides the setup function to intercept standard library logging
and route it through a structlog pipeline that outputs JSON and injects
request context (correlation_id and request_id).
"""

import logging

import structlog

from .context import get_request_context


def _inject_request_context(logger: logging.Logger, log_method: str, event_dict: dict) -> dict:
    """Structlog processor to inject request context."""
    context = get_request_context()
    if context.get("request_id"):
        event_dict["request_id"] = context["request_id"]
    if context.get("correlation_id"):
        event_dict["correlation_id"] = context["correlation_id"]
    return event_dict


def setup_logging() -> None:
    """Configure structlog and route standard library logging to it."""
    # Configure structlog processors
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_request_context,
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Route standard library logging to structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            _inject_request_context,
        ],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
